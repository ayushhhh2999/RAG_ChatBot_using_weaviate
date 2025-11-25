-- Fix search path for delete_old_messages function
CREATE OR REPLACE FUNCTION public.delete_old_messages()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  DELETE FROM public.chat_messages
  WHERE created_at < now() - interval '10 days';
END;
$$;