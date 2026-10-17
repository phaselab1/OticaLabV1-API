import { ConflictException, ForbiddenException } from '@nestjs/common';
import { AppointmentStatus, UserRole } from '@/common/enums';
import { User } from '@/modules/users/entities/user.entity';
import { AppointmentsService } from './appointments.service';
import { Appointment } from './entities/appointment.entity';

describe('AppointmentsService - Business Rules', () => {
  let service: AppointmentsService;
  let mockAppointmentRepo: any;
  let mockCustomersService: any;
  let mockCustomerRepo: any;
  let mockCompanyUserService: any;

  beforeEach(() => {
    mockAppointmentRepo = {
      getById: vi.fn(),
      updateWithHistory: vi.fn(),
      updateLeadInfo: vi.fn(),
    };
    mockCustomerRepo = {
      getByIdentity: vi.fn(),
      create: vi.fn(),
    };
    mockCustomersService = {
      getCustomerRepository: vi.fn().mockReturnValue(mockCustomerRepo),
    };
    mockCompanyUserService = {
      hasUnitAccess: vi.fn(),
    };

    service = new AppointmentsService(
      mockAppointmentRepo,
      mockCustomersService,
      mockCompanyUserService,
    );
  });

  it('attended appointment cannot be edited or rescheduled by attendant', async () => {
    const attendant = new User({
      id: 'att-1',
      role: UserRole.ATTENDANT,
    });

    const appointment = new Appointment({
      id: 'apt-1',
      company_id: 'comp-1',
      company_unit_id: 'unit-1',
      status: AppointmentStatus.ATTENDED,
    });

    mockAppointmentRepo.getById.mockResolvedValue(appointment);
    mockCompanyUserService.hasUnitAccess.mockResolvedValue(true);

    await expect(
      service.update(
        'apt-1',
        { status: AppointmentStatus.ATTENDED },
        attendant,
      ),
    ).rejects.toThrow(ForbiddenException);

    await expect(
      service.reschedule(
        'apt-1',
        { scheduled_at: '2026-10-15T15:00:00Z' },
        attendant,
      ),
    ).rejects.toThrow(ForbiddenException);
  });

  it('lead name and phone cannot be updated if already promoted to customer', async () => {
    const admin = new User({
      id: 'admin-1',
      role: UserRole.ADMIN,
    });

    const appointment = new Appointment({
      id: 'apt-1',
      company_id: 'comp-1',
      company_unit_id: 'unit-1',
      status: AppointmentStatus.ATTENDED,
      customer_id: 'cust-1',
    });

    mockAppointmentRepo.getById.mockResolvedValue(appointment);
    mockCompanyUserService.hasUnitAccess.mockResolvedValue(true);

    await expect(
      service.update(
        'apt-1',
        { lead_full_name: 'Novo Nome' },
        admin,
      ),
    ).rejects.toThrow(ForbiddenException);
  });

  it('marking status attended promotes lead to customer automatically', async () => {
    const admin = new User({
      id: 'admin-1',
      role: UserRole.ADMIN,
    });

    const appointment = new Appointment({
      id: 'apt-1',
      company_id: 'comp-1',
      company_unit_id: 'unit-1',
      lead_full_name: 'Carlos Oliveira',
      lead_phone: '11999999999',
      status: AppointmentStatus.SCHEDULED,
      customer_id: null,
    });

    mockAppointmentRepo.getById.mockResolvedValue(appointment);
    mockCompanyUserService.hasUnitAccess.mockResolvedValue(true);
    mockCustomerRepo.getByIdentity.mockResolvedValue(null);
    mockCustomerRepo.create.mockResolvedValue({ id: 'new-cust-1' });

    mockAppointmentRepo.updateWithHistory.mockResolvedValue(
      new Appointment({
        ...appointment,
        status: AppointmentStatus.ATTENDED,
        customer_id: 'new-cust-1',
      }),
    );

    const result = await service.update(
      'apt-1',
      { status: AppointmentStatus.ATTENDED },
      admin,
    );

    expect(mockCustomerRepo.create).toHaveBeenCalledWith(
      expect.objectContaining({
        company_id: 'comp-1',
        company_unit_id: 'unit-1',
        full_name: 'Carlos Oliveira',
        phone: '11999999999',
      }),
    );
    expect(mockAppointmentRepo.updateWithHistory).toHaveBeenCalledWith(
      'apt-1',
      'admin-1',
      expect.objectContaining({
        customerId: 'new-cust-1',
        status: AppointmentStatus.ATTENDED,
      }),
    );
    expect(result.customer_id).toBe('new-cust-1');
  });
});

