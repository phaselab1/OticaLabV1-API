export interface AppConfig {
  supabaseUrl: string;
  supabaseKey: string;
  secretKey: string;
  debug: boolean;
  corsAllowedOrigins: string[];
  port: number;
  kommoEncryptionKey: string;
  kommoWorkerEnabled: boolean;
  kommoWorkerBatchSize: number;
}

export default (): { app: AppConfig } => {
  const corsRaw = process.env.CORS_ALLOWED_ORIGINS || '';
  const corsAllowedOrigins = corsRaw
    .split(',')
    .map((o) => o.trim())
    .filter((o) => o.length > 0);

  return {
    app: {
      supabaseUrl: process.env.SUPABASE_URL || 'http://localhost:8000',
      supabaseKey: process.env.SUPABASE_KEY || '',
      secretKey: process.env.SECRET_KEY || 'default-secret-key',
      debug: process.env.DEBUG === 'true',
      corsAllowedOrigins,
      port: parseInt(process.env.PORT || '8000', 10),
      kommoEncryptionKey: process.env.KOMMO_ENCRYPTION_KEY || '',
      kommoWorkerEnabled: process.env.KOMMO_WORKER_ENABLED !== 'false',
      kommoWorkerBatchSize: parseInt(process.env.KOMMO_WORKER_BATCH_SIZE || '10', 10),
    },
  };
};

