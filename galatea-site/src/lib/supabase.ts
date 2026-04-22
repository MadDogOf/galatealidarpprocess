import { createBrowserClient } from '@supabase/ssr'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://bqplslkpphtsqbbuoqyr.supabase.co';
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJxcGxzbGtwcGh0c3FiYnVvcXlyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMjI1NDQsImV4cCI6MjA5MDY5ODU0NH0.tOFsNGKwqgdu7yEA0JYRqj_DM7jbmbg9aHpJgW0OyGg';

export const supabase = createBrowserClient(supabaseUrl, supabaseKey);
