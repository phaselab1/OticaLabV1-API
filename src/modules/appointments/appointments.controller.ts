import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  Patch,
  Post,
  Put,
  Query,
  UseGuards,
} from "@nestjs/common";
import {
  ApiBearerAuth,
  ApiOperation,
  ApiQuery,
  ApiResponse,
  ApiTags,
} from "@nestjs/swagger";
import { PageDto, PaginationParamsDto } from "@/common/dto/pagination.dto";
import { AppointmentStatus } from "@/common/enums";
import { CurrentUser } from "@/modules/auth/decorators/current-user.decorator";
import { JwtAuthGuard } from "@/modules/auth/guards/jwt-auth.guard";
import { RolesGuard } from "@/modules/auth/guards/roles.guard";
import { User } from "@/modules/users/entities/user.entity";
import {
  AppointmentHistoryService,
  AppointmentsService,
} from "./appointments.service";
import {
  AppointmentHistoryResponseDto,
  AppointmentResponseDto,
  CreateAppointmentDto,
  RescheduleAppointmentDto,
  UpdateAppointmentDto,
} from "./dto/appointment.dto";
import {
  Appointment,
  AppointmentHistoryEntry,
} from "./entities/appointment.entity";

@ApiTags("appointments")
@ApiBearerAuth()
@UseGuards(JwtAuthGuard, RolesGuard)
@Controller("appointments")
export class AppointmentsController {
  constructor(
    private readonly appointmentsService: AppointmentsService,
    private readonly historyService: AppointmentHistoryService,
  ) {}

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({ summary: "Criar agendamento" })
  @ApiResponse({ status: 201, type: AppointmentResponseDto })
  async create(
    @Body() body: CreateAppointmentDto,
    @CurrentUser() currentUser: User,
  ): Promise<Appointment> {
    return this.appointmentsService.create(body, currentUser);
  }

  @Get()
  @ApiOperation({ summary: "Listar agendamentos" })
  @ApiQuery({ name: "company_id", required: false, type: String })
  @ApiQuery({ name: "company_unit_id", required: false, type: String })
  @ApiQuery({ name: "customer_id", required: false, type: String })
  @ApiQuery({ name: "status", required: false, enum: AppointmentStatus })
  @ApiResponse({ status: 200, type: PageDto<AppointmentResponseDto> })
  async getAll(
    @CurrentUser() currentUser: User,
    @Query() query: PaginationParamsDto,
    @Query("company_id") companyId?: string,
    @Query("company_unit_id") companyUnitId?: string,
    @Query("customer_id") customerId?: string,
    @Query("status") status?: AppointmentStatus,
  ): Promise<PageDto<Appointment>> {
    return this.appointmentsService.getAll(
      currentUser,
      query.page || 1,
      query.page_size || 20,
      companyId,
      companyUnitId,
      customerId,
      status,
    );
  }

  @Get(":id")
  @ApiOperation({ summary: "Buscar agendamento por ID" })
  @ApiResponse({ status: 200, type: AppointmentResponseDto })
  async getById(
    @Param("id") id: string,
    @CurrentUser() currentUser: User,
  ): Promise<Appointment> {
    return this.appointmentsService.getById(id, currentUser);
  }

  @Get(":id/history")
  @ApiOperation({ summary: "Histórico de alterações do agendamento" })
  @ApiResponse({ status: 200, type: PageDto<AppointmentHistoryResponseDto> })
  async getHistory(
    @Param("id") id: string,
    @CurrentUser() currentUser: User,
    @Query() query: PaginationParamsDto,
  ): Promise<PageDto<AppointmentHistoryEntry>> {
    return this.historyService.getByAppointment(
      id,
      currentUser,
      query.page || 1,
      query.page_size || 20,
    );
  }

  @Put(":id")
  @ApiOperation({ summary: "Atualizar agendamento" })
  @ApiResponse({ status: 200, type: AppointmentResponseDto })
  async update(
    @Param("id") id: string,
    @Body() body: UpdateAppointmentDto,
    @CurrentUser() currentUser: User,
  ): Promise<Appointment> {
    return this.appointmentsService.update(id, body, currentUser);
  }

  @Patch(":id/reschedule")
  @ApiOperation({ summary: "Reagendar agendamento" })
  @ApiResponse({ status: 200, type: AppointmentResponseDto })
  async reschedule(
    @Param("id") id: string,
    @Body() body: RescheduleAppointmentDto,
    @CurrentUser() currentUser: User,
  ): Promise<Appointment> {
    return this.appointmentsService.reschedule(id, body, currentUser);
  }

  @Delete(":id")
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: "Excluir agendamento" })
  @ApiResponse({ status: 204, description: "Agendamento removido." })
  async delete(
    @Param("id") id: string,
    @CurrentUser() currentUser: User,
  ): Promise<void> {
    return this.appointmentsService.delete(id, currentUser);
  }
}
