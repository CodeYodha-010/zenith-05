import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = (import.meta.env.VITE_SUPABASE_URL as string | undefined) ?? '';
const supabasePublishableKey =
  (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined) ?? '';

// The client is created only when the deployment supplies public build vars.
// This keeps local Django-auth development possible without Supabase secrets.
export const supabase: SupabaseClient | null =
  supabaseUrl && supabasePublishableKey
    ? createClient(supabaseUrl, supabasePublishableKey, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
          storageKey: 'zenith-supabase-auth',
        },
      })
    : null;

export const isSupabaseConfigured = Boolean(supabase);
