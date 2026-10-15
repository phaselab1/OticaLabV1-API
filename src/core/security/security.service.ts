import { Injectable } from "@nestjs/common";
import * as bcrypt from "bcryptjs";

const DUMMY_PASSWORD_HASH = bcrypt.hashSync(
  "dummy-password-for-timing-safety",
  bcrypt.genSaltSync(10),
);

@Injectable()
export class SecurityService {
  readonly dummyPasswordHash = DUMMY_PASSWORD_HASH;

  hashPassword(password: string): string {
    return bcrypt.hashSync(password, bcrypt.genSaltSync(10));
  }

  verifyPassword(plain: string, hash: string): boolean {
    return bcrypt.compareSync(plain, hash);
  }
}
