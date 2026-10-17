export interface AppConfig {
  supabaseUrl: string;
  supabaseKey: string;
  secretKey: string;
  debug: boolean;
  corsAllowedOrigins: string[];
  port: number;
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
    },
  };
};

