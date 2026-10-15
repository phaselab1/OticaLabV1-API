import {
  CallHandler,
  ExecutionContext,
  Injectable,
  NestInterceptor,
} from '@nestjs/common';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

export interface ResponseFormat<T> {
  data: T;
  meta?: {
    timestamp: string;
    path: string;
  };
}

@Injectable()
export class ResponseTransformInterceptor<T>
  implements NestInterceptor<T, any>
{
  intercept(context: ExecutionContext, next: CallHandler): Observable<any> {
    const request = context.switchToHttp().getRequest();

    // Endpoints like /health or swagger docs should not be altered
    if (request.url?.startsWith('/health') || request.url?.startsWith('/docs')) {
      return next.handle();
    }

    return next.handle().pipe(
      map((data) => {
        return data;
      }),
    );
  }
}

