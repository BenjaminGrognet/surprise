import { afterAll } from '@jest/globals';
import { supabase } from '@/lib/supabase';

// The client refreshes its session on a timer: stopped, so that Jest ends with the tests.
afterAll(() => supabase.auth.stopAutoRefresh());
