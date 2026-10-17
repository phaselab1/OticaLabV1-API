import { forwardRef, Module } from '@nestjs/common';
import { CompaniesModule } from '@/modules/companies/companies.module';
import { CustomersModule } from '@/modules/customers/customers.module';
import { AppointmentsController } from './appointments.controller';
import {
  AppointmentHistoryService,
  AppointmentsService,
} from './appointments.service';
import {
  AppointmentHistoryRepository,
  AppointmentRepository,
} from './repositories/appointment.repository';

@Module({
  imports: [
    forwardRef(() => CompaniesModule),
    forwardRef(() => CustomersModule),
  ],
  controllers: [AppointmentsController],
  providers: [
    AppointmentsService,
    AppointmentHistoryService,
    AppointmentRepository,
    AppointmentHistoryRepository,
  ],
  exports: [
    AppointmentsService,
    AppointmentHistoryService,
    AppointmentRepository,
    AppointmentHistoryRepository,
  ],
})
export class AppointmentsModule {}

