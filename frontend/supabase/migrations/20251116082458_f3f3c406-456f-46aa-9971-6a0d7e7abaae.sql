-- Create chat_messages table to store chat history
CREATE TABLE public.chat_messages (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

-- Create policy to allow anyone to read messages (public chat)
CREATE POLICY "Anyone can view messages"
  ON public.chat_messages
  FOR SELECT
  USING (true);

-- Create policy to allow anyone to insert messages
CREATE POLICY "Anyone can insert messages"
  ON public.chat_messages
  FOR INSERT
  WITH CHECK (true);

-- Create index for faster queries
CREATE INDEX idx_chat_messages_created_at ON public.chat_messages(created_at DESC);

-- Create function to delete messages older than 10 days
CREATE OR REPLACE FUNCTION public.delete_old_messages()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  DELETE FROM public.chat_messages
  WHERE created_at < now() - interval '10 days';
END;
$$;

-- Create trigger to automatically clean up old messages daily
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule cleanup to run daily at midnight
SELECT cron.schedule(
  'delete-old-chat-messages',
  '0 0 * * *',
  'SELECT public.delete_old_messages();'
);