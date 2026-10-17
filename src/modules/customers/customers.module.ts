import { forwardRef, Module } from '@nestjs/common';
import { CompaniesModule } from '@/modules/companies/companies.module';
import { CustomersController } from './customers.controller';
import { CustomersService } from './customers.service';
import { CustomerMatchingService } from './customer-matching.service';
import { CustomerRepository } from './repositories/customer.repository';

@Module({
  imports: [forwardRef(() => CompaniesModule)],
  controllers: [CustomersController],
  providers: [CustomersService, CustomerRepository, CustomerMatchingService],
  exports: [CustomersService, CustomerRepository, CustomerMatchingService],
})
export class CustomersModule {}

