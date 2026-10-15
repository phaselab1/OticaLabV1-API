import { ConflictException } from '@nestjs/common';
import { CustomerMatchingService } from './customer-matching.service';

describe('CustomerMatchingService', () => {
  let repo: any;
  let service: CustomerMatchingService;
  const base = {
    companyId: 'comp-1',
    companyUnitId: 'unit-1',
    userId: 'u-1',
    fullName: 'Maria da Silva',
    phone: '63991234567',
  };

  beforeEach(() => {
    repo = {
      findByKommoContactId: vi.fn().mockResolvedValue(null),
      matchByPhone: vi.fn().mockResolvedValue([]),
      create: vi.fn().mockResolvedValue({ id: 'cust-new' }),
      linkKommoContact: vi.fn().mockResolvedValue(undefined),
    };
    service = new CustomerMatchingService(repo);
  });

  it('kommo_contact_id vence tudo', async () => {
    repo.findByKommoContactId.mockResolvedValue({ id: 'cust-k' });
    await expect(service.resolve({ ...base, kommoContactId: 9 })).resolves.toEqual({
      customerId: 'cust-k',
      created: false,
      reviewReason: null,
    });
    expect(repo.matchByPhone).not.toHaveBeenCalled();
  });

  it('telefone + nome parecido (>= 0.85) reutiliza e vincula o contato', async () => {
    repo.matchByPhone.mockResolvedValue([{ id: 'cust-m', score: 0.92 }]);
    await expect(service.resolve({ ...base, kommoContactId: 9 })).resolves.toEqual({
      customerId: 'cust-m',
      created: false,
      reviewReason: null,
    });
    expect(repo.matchByPhone).toHaveBeenCalledWith(
      'comp-1',
      ['63991234567', '6391234567'],
      'Maria da Silva',
    );
    expect(repo.linkKommoContact).toHaveBeenCalledWith('cust-m', 9, 'u-1');
    expect(repo.create).not.toHaveBeenCalled();
  });

  it('mesmo telefone, outro membro da família (< 0.6) → cria sem revisão', async () => {
    repo.matchByPhone.mockResolvedValue([{ id: 'cust-pai', score: 0.2 }]);
    await expect(service.resolve(base)).resolves.toEqual({
      customerId: 'cust-new',
      created: true,
      reviewReason: null,
    });
    expect(repo.create).toHaveBeenCalledWith({
      company_id: 'comp-1',
      company_unit_id: 'unit-1',
      full_name: 'Maria da Silva',
      phone: '63991234567',
      kommo_contact_id: null,
      needs_review: false,
      review_reason: null,
      created_by_user_id: 'u-1',
      updated_by_user_id: 'u-1',
    });
  });

  it('nome quase igual (0.6–0.85) → cria com possível duplicado', async () => {
    repo.matchByPhone.mockResolvedValue([{ id: 'cust-x', score: 0.7 }]);
    await expect(service.resolve(base)).resolves.toEqual({
      customerId: 'cust-new',
      created: true,
      reviewReason: 'Possível duplicado de cust-x',
    });
    expect(repo.create).toHaveBeenCalledWith(
      expect.objectContaining({ needs_review: true, review_reason: 'Possível duplicado de cust-x' }),
    );
  });

  it('sem telefone → cria direto, sem buscar candidatos', async () => {
    await service.resolve({ ...base, phone: null });
    expect(repo.matchByPhone).not.toHaveBeenCalled();
    expect(repo.create).toHaveBeenCalledWith(expect.objectContaining({ phone: null }));
  });

  it('corrida no kommo_contact_id: usa o cliente que venceu', async () => {
    repo.create.mockRejectedValue(new ConflictException('x'));
    repo.findByKommoContactId.mockResolvedValueOnce(null).mockResolvedValueOnce({ id: 'cust-race' });
    await expect(service.resolve({ ...base, kommoContactId: 9 })).resolves.toEqual({
      customerId: 'cust-race',
      created: false,
      reviewReason: null,
    });
  });

  it('conflito sem contato Kommo propaga', async () => {
    repo.create.mockRejectedValue(new ConflictException('x'));
    await expect(service.resolve(base)).rejects.toBeInstanceOf(ConflictException);
  });
});
