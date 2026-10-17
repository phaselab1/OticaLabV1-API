import { Body, Controller, Get, Post, UseGuards } from '@nestjs/common';
import {
  ApiBearerAuth,
  ApiOperation,
  ApiResponse,
  ApiTags,
} from '@nestjs/swagger';
import { UserResponseDto } from '@/modules/users/dto/user.dto';
import { User } from '@/modules/users/entities/user.entity';
import { AuthService } from './auth.service';
import { CurrentUser } from './decorators/current-user.decorator';
import { LoginRequestDto, TokenResponseDto } from './dto/auth.dto';
import { JwtAuthGuard } from './guards/jwt-auth.guard';

@ApiTags('auth')
@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('login')
  @ApiOperation({ summary: 'Login' })
  @ApiResponse({
    status: 200,
    description: 'Sucesso.',
    type: TokenResponseDto,
  })
  @ApiResponse({
    status: 401,
    description: 'E-mail ou senha inválidos.',
  })
  @ApiResponse({
    status: 429,
    description:
      'Mais de 5 tentativas com falha para este e-mail nos últimos 15 minutos. Aguarde antes de tentar novamente.',
  })
  async login(@Body() body: LoginRequestDto): Promise<TokenResponseDto> {
    const token = await this.authService.login(body.email, body.password);
    return {
      access_token: token,
      token_type: 'bearer',
    };
  }

  @Get('me')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Perfil autenticado' })
  @ApiResponse({
    status: 200,
    description: 'Perfil do usuário retornado.',
    type: UserResponseDto,
  })
  @ApiResponse({
    status: 401,
    description: 'Token ausente, inválido ou expirado.',
  })
  getMe(@CurrentUser() user: User): User {
    return user;
  }
}

