import { forwardRef, Module } from '@nestjs/common';
import { UsersModule } from '@/modules/users/users.module';
import { CompaniesController } from './companies.controller';
import {
  CompaniesService,
  CompanyUnitsService,
  CompanyUserService,
} from './companies.service';
import {
  CompanyRepository,
  CompanyUnitRepository,
  CompanyUserRepository,
} from './repositories/company.repository';

@Module({
  imports: [forwardRef(() => UsersModule)],
  controllers: [CompaniesController],
  providers: [
    CompaniesService,
    CompanyUnitsService,
    CompanyUserService,
    CompanyRepository,
    CompanyUnitRepository,
    CompanyUserRepository,
  ],
  exports: [
    CompaniesService,
    CompanyUnitsService,
    CompanyUserService,
    CompanyRepository,
    CompanyUnitRepository,
    CompanyUserRepository,
  ],
})
export class CompaniesModule {}

