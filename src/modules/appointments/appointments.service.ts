import {
  ConflictException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { PageDto } from '@/common/dto/pagination.dto';
import { AppointmentStatus, UserRole } from '@/common/enums';
import { formatTitleCase } from '@/common/utils/text.util';
import { CompanyUserService } from '@/modules/companies/companies.service';
import { CustomersService } from '@/modules/customers/customers.service';
import { User } from '@/modules/users/entities/user.entity';
import {
  CreateAppointmentDto,
  RescheduleAppointmentDto,
  UpdateAppointmentDto,
} from './dto/appointment.dto';
import {
  Appointment,
  AppointmentHistoryEntry,
} from './entities/appointment.entity';
import {
  AppointmentHistoryRepository,
  AppointmentRepository,
} from './repositories/appointment.repository';

@Injectable()
export class AppointmentsService {
  constructor(
    private readonly repository: AppointmentRepository,
    private readonly customersService: CustomersService,
    private readonly companyUserService: CompanyUserService,
  ) {}

  private async getWithAccessCheck(
    appointmentId: string,
    currentUser: User,
  ): Promise<Appointment> {
    const appointment = await this.repository.getById(appointmentId);
    if (!appointment) {
      throw new NotFoundException(`Agendamento '${appointmentId}' não encontrado`);
    }

    if (currentUser.role === UserRole.SUPER_ADMIN) {
      return appointment;
    }

    const hasAccess = await this.companyUserService.hasUnitAccess(
      currentUser,
      appointment.company_id,
      appointment.company_unit_id,
    );
    if (!hasAccess) {
      throw new ForbiddenException(
        'Você não tem permissão para acessar os agendamentos desta unidade.',
      );
    }

    return appointment;
  }

  async create(
    data: CreateAppointmentDto,
    currentUser: User,
  ): Promise<Appointment> {
    const [companyId, companyUnitId] =
      await this.companyUserService.resolveCompanyAndUnit(
        currentUser,
        data.company_id,
        data.company_unit_id,
      );

    return this.repository.create({
      company_id: companyId,
      company_unit_id: companyUnitId,
      lead_full_name: formatTitleCase(data.lead_full_name),
      lead_phone: data.lead_phone,
      scheduled_at: data.scheduled_at,
      status: AppointmentStatus.SCHEDULED,
      notes: data.notes || null,
      created_by_user_id: currentUser.id,
      updated_by_user_id: currentUser.id,
    });
  }

  async getAll(
    currentUser: User,
    page: number = 1,
    pageSize: number = 20,
    companyId?: string | null,
    companyUnitId?: string | null,
    customerId?: string | null,
    status?: AppointmentStatus | null,
  ): Promise<PageDto<Appointment>> {
    let resolvedCompanyId = companyId;
    let resolvedUnitId = companyUnitId;

    if (currentUser.role !== UserRole.SUPER_ADMIN) {
      [resolvedCompanyId, resolvedUnitId] =
        await this.companyUserService.resolveScopeForList(
          currentUser,
          companyId,
          companyUnitId,
        );
    }

    if (resolvedCompanyId === '__none__') {
      return new PageDto([], page, pageSize, 0);
    }

    const [items, total] = await this.repository.getAll(
      page,
      pageSize,
      resolvedCompanyId,
      resolvedUnitId,
      customerId,
      status,
    );
    return new PageDto(items, page, pageSize, total);
  }

  async getById(
    appointmentId: string,
    currentUser: User,
  ): Promise<Appointment> {
    return this.getWithAccessCheck(appointmentId, currentUser);
  }

  private async promoteLeadToCustomer(
    appointment: Appointment,
    currentUser: User,
  ): Promise<string> {
    const customerRepo = this.customersService.getCustomerRepository();
    const existingCustomer = await customerRepo.getByIdentity(
      appointment.company_id,
      appointment.lead_full_name,
    );
    if (existingCustomer) {
      return existingCustomer.id;
    }

    try {
      const created = await customerRepo.create({
        company_id: appointment.company_id,
        company_unit_id: appointment.company_unit_id,
        full_name: appointment.lead_full_name,
        phone: appointment.lead_phone,
        created_by_user_id: currentUser.id,
        updated_by_user_id: currentUser.id,
      });
      return created.id;
    } catch (err: any) {
      if (err instanceof ConflictException) {
        // Race condition handling
        const concurrent = await customerRepo.getByIdentity(
          appointment.company_id,
          appointment.lead_full_name,
        );
        if (concurrent) {
          return concurrent.id;
        }
      }
      throw err;
    }
  }

  async update(
    appointmentId: string,
    data: UpdateAppointmentDto,
    currentUser: User,
  ): Promise<Appointment> {
    const existing = await this.getWithAccessCheck(appointmentId, currentUser);

    if (
      existing.status === AppointmentStatus.ATTENDED &&
      currentUser.role === UserRole.ATTENDANT
    ) {
      throw new ForbiddenException(
        'Agendamento já marcado como comparecido não pode ser alterado por atendente.',
      );
    }

    if (
      (existing.customer_id !== null ||
        existing.status === AppointmentStatus.ATTENDED) &&
      (data.lead_full_name !== undefined || data.lead_phone !== undefined)
    ) {
      throw new ForbiddenException(
        'Nome e telefone só podem ser alterados enquanto o agendamento não for cliente.',
      );
    }

    if (data.lead_full_name !== undefined || data.lead_phone !== undefined) {
      const newLeadName =
        data.lead_full_name !== undefined
          ? formatTitleCase(data.lead_full_name)
          : undefined;
      await this.repository.updateLeadInfo(
        appointmentId,
        currentUser.id,
        newLeadName,
        data.lead_phone,
        data.lead_phone !== undefined,
      );
    }

    let customerId: string | null = null;
    if (
      data.status === AppointmentStatus.ATTENDED &&
      existing.customer_id === null
    ) {
      customerId = await this.promoteLeadToCustomer(existing, currentUser);
    }

    const subject =
      existing.lead_full_name || `o cliente ${existing.customer_id}`;
    const appointment = await this.repository.updateWithHistory(
      appointmentId,
      currentUser.id,
      {
        scheduledAt: data.scheduled_at,
        status: data.status,
        notes: data.notes,
        notesProvided: data.notes !== undefined,
        customerId,
        subject,
      },
    );

    if (!appointment) {
      throw new NotFoundException(`Agendamento '${appointmentId}' não encontrado`);
    }
    return appointment;
  }

  async reschedule(
    appointmentId: string,
    data: RescheduleAppointmentDto,
    currentUser: User,
  ): Promise<Appointment> {
    const existing = await this.getWithAccessCheck(appointmentId, currentUser);

    if (
      existing.status === AppointmentStatus.ATTENDED &&
      currentUser.role === UserRole.ATTENDANT
    ) {
      throw new ForbiddenException(
        'Agendamento já marcado como comparecido não pode ser reagendado por atendente.',
      );
    }

    const subject =
      existing.lead_full_name || `o cliente ${existing.customer_id}`;
    const appointment = await this.repository.updateWithHistory(
      appointmentId,
      currentUser.id,
      {
        scheduledAt: data.scheduled_at,
        status: null,
        notes: data.notes,
        notesProvided: data.notes !== undefined,
        subject,
      },
    );

    if (!appointment) {
      throw new NotFoundException(`Agendamento '${appointmentId}' não encontrado`);
    }
    return appointment;
  }

  async delete(appointmentId: string, currentUser: User): Promise<void> {
    await this.getWithAccessCheck(appointmentId, currentUser);
    const deleted = await this.repository.softDelete(appointmentId);
    if (!deleted) {
      throw new NotFoundException(`Agendamento '${appointmentId}' não encontrado`);
    }
  }
}

@Injectable()
export class AppointmentHistoryService {
  constructor(
    private readonly historyRepo: AppointmentHistoryRepository,
    private readonly appointmentRepo: AppointmentRepository,
    private readonly companyUserService: CompanyUserService,
  ) {}

  async getByAppointment(
    appointmentId: string,
    currentUser: User,
    page: number = 1,
    pageSize: number = 20,
  ): Promise<PageDto<AppointmentHistoryEntry>> {
    const appointment = await this.appointmentRepo.getById(appointmentId);
    if (!appointment) {
      throw new NotFoundException(`Agendamento '${appointmentId}' não encontrado`);
    }

    if (currentUser.role !== UserRole.SUPER_ADMIN) {
      const hasAccess = await this.companyUserService.hasUnitAccess(
        currentUser,
        appointment.company_id,
        appointment.company_unit_id,
      );
      if (!hasAccess) {
        throw new ForbiddenException(
          'Você não tem permissão para acessar os agendamentos desta unidade.',
        );
      }
    }

    const [items, total] = await this.historyRepo.getByAppointmentId(
      appointmentId,
      page,
      pageSize,
    );
    return new PageDto(items, page, pageSize, total);
  }
}

