import { ApiProperty } from "@nestjs/swagger";
import { IsEmail, IsNotEmpty, IsString, MaxLength } from "class-validator";

export class LoginRequestDto {
  @ApiProperty({
    description: "E-mail cadastrado do usuário.",
    example: "admin@oticalab.com",
    maxLength: 255,
  })
  @IsEmail()
  @IsNotEmpty()
  @MaxLength(255)
  email: string;

  @ApiProperty({
    description:
      "Senha em texto plano — nunca armazenada, só usada para verificação.",
    maxLength: 72,
  })
  @IsString()
  @IsNotEmpty()
  @MaxLength(72)
  password: string;
}

export class TokenResponseDto {
  @ApiProperty({
    description: "Token JWT — envie em `Authorization: Bearer <token>`.",
  })
  access_token: string;

  @ApiProperty({
    description: "Sempre `bearer`.",
    default: "bearer",
  })
  token_type: string = "bearer";
}
