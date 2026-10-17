import { forwardRef, Module } from '@nestjs/common';
import { CompaniesModule } from '@/modules/companies/companies.module';
import { CustomersController } from './customers.controller';
import { CustomersService } from './customers.service';
import { CustomerRepository } from './repositories/customer.repository';

@Module({
  imports: [forwardRef(() => CompaniesModule)],
  controllers: [CustomersController],
  providers: [CustomersService, CustomerRepository],
  exports: [CustomersService, CustomerRepository],
})
export class CustomersModule {}

