import { ArgumentsHost, HttpException, HttpStatus } from '@nestjs/common';
import {
  AllExceptionsFilter,
  BUSINESS_RULE_VIOLATION,
  FOREIGN_KEY_VIOLATION,
  INVALID_TEXT_REPRESENTATION,
} from './all-exceptions.filter';

describe('AllExceptionsFilter', () => {
  let filter: AllExceptionsFilter;
  let mockStatus: any;
  let mockJson: any;
  let mockResponse: any;
  let mockHost: ArgumentsHost;

  beforeEach(() => {
    filter = new AllExceptionsFilter();
    mockJson = vi.fn();
    mockStatus = vi.fn().mockReturnValue({ json: mockJson });
    mockResponse = { status: mockStatus };

    mockHost = {
      switchToHttp: vi.fn().mockReturnValue({
        getResponse: vi.fn().mockReturnValue(mockResponse),
        getRequest: vi.fn().mockReturnValue({ method: 'GET', url: '/test' }),
      }),
    } as any;
  });

  it('translates HttpException correctly', () => {
    const exc = new HttpException('Bad input data', HttpStatus.BAD_REQUEST);
    filter.catch(exc, mockHost);

    expect(mockStatus).toHaveBeenCalledWith(HttpStatus.BAD_REQUEST);
    expect(mockJson).toHaveBeenCalledWith({ detail: 'Bad input data' });
  });

  it('translates PostgreSQL 22P02 invalid UUID to 404', () => {
    const error = { code: INVALID_TEXT_REPRESENTATION, message: 'invalid syntax for uuid' };
    filter.catch(error, mockHost);

    expect(mockStatus).toHaveBeenCalledWith(HttpStatus.NOT_FOUND);
    expect(mockJson).toHaveBeenCalledWith({ detail: 'Resource not found' });
  });

  it('translates PostgreSQL 23503 foreign key violation to 404', () => {
    const error = { code: FOREIGN_KEY_VIOLATION, message: 'fk violated' };
    filter.catch(error, mockHost);

    expect(mockStatus).toHaveBeenCalledWith(HttpStatus.NOT_FOUND);
    expect(mockJson).toHaveBeenCalledWith({ detail: 'Referenced resource not found' });
  });

  it('translates PostgreSQL P0001 business rule violation trigger to 400 with detail', () => {
    const error = { code: BUSINESS_RULE_VIOLATION, message: 'User does not belong to company' };
    filter.catch(error, mockHost);

    expect(mockStatus).toHaveBeenCalledWith(HttpStatus.BAD_REQUEST);
    expect(mockJson).toHaveBeenCalledWith({ detail: 'User does not belong to company' });
  });

  it('falls back to 500 for unhandled exceptions without leaking stack trace', () => {
    const error = new Error('unexpected crash');
    filter.catch(error, mockHost);

    expect(mockStatus).toHaveBeenCalledWith(HttpStatus.INTERNAL_SERVER_ERROR);
    expect(mockJson).toHaveBeenCalledWith({ detail: 'Internal Server Error' });
  });
});

