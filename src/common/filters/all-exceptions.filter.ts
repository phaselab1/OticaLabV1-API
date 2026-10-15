import {
  ExceptionFilter,
  Catch,
  ArgumentsHost,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { Response, Request } from 'express';

export const INVALID_TEXT_REPRESENTATION = '22P02';
export const FOREIGN_KEY_VIOLATION = '23503';
export const BUSINESS_RULE_VIOLATION = 'P0001';

@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  private readonly logger = new Logger(AllExceptionsFilter.name);

  catch(exception: any, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request>();

    if (exception instanceof HttpException) {
      const status = exception.getStatus();
      const exceptionResponse = exception.getResponse();

      let detail: any;
      if (typeof exceptionResponse === 'string') {
        detail = exceptionResponse;
      } else if (
        typeof exceptionResponse === 'object' &&
        exceptionResponse !== null
      ) {
        detail =
          (exceptionResponse as any).message ||
          (exceptionResponse as any).detail ||
          exceptionResponse;
        if (Array.isArray(detail)) {
          detail = detail.join(', ');
        }
      }

      return response.status(status).json({ detail });
    }

    // PostgREST APIError mapping
    if (exception?.code) {
      if (exception.code === INVALID_TEXT_REPRESENTATION) {
        return response
          .status(HttpStatus.NOT_FOUND)
          .json({ detail: 'Resource not found' });
      }

      if (exception.code === FOREIGN_KEY_VIOLATION) {
        return response
          .status(HttpStatus.NOT_FOUND)
          .json({ detail: 'Referenced resource not found' });
      }

      if (exception.code === BUSINESS_RULE_VIOLATION) {
        return response
          .status(HttpStatus.BAD_REQUEST)
          .json({ detail: exception.message || 'Bad request' });
      }
    }

    this.logger.error(
      `Unhandled error on ${request.method} ${request.url}`,
      exception?.stack || exception,
    );

    return response
      .status(HttpStatus.INTERNAL_SERVER_ERROR)
      .json({ detail: 'Internal Server Error' });
  }
}

