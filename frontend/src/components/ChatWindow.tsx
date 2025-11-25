import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Bot, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { toast } from "sonner";
import { supabase } from "@/integrations/supabase/client";

const API_BASE_URL = "http://localhost:8000";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
}

const ChatWindow = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load chat history from database
  useEffect(() => {
    const loadChatHistory = async () => {
      try {
        const { data, error } = await supabase
          .from('chat_messages')
          .select('*')
          .order('created_at', { ascending: true });

        if (error) throw error;

        if (data) {
          setMessages(data.map(msg => ({
            role: msg.role as 'user' | 'assistant',
            content: msg.content
          })));
        }
      } catch (error) {
        console.error('Error loading chat history:', error);
        toast.error('Failed to load chat history');
      } finally {
        setIsLoadingHistory(false);
      }
    };

    loadChatHistory();
  }, []);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: "user",
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    // Silent background memory call
    fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        chat: input,
      }),
    }).catch(() => {});

    // Save user message to database
    supabase
      .from('chat_messages')
      .insert({
        role: 'user',
        content: input,
      })
      .then(({ error }) => {
        if (error) console.error('Error saving user message:', error);
      });

    try {
      const response = await fetch(`${API_BASE_URL}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: input,
          top_k: 4,
        }),
      });

      if (!response.ok) throw new Error("Failed to get response");

      const data = await response.json();

      // Remove sources text from the answer
      const cleanAnswer = data.answer.replace(/\s*\(Sources?:.*?\)\s*$/i, '').trim();

      const assistantMessage: Message = {
        role: "assistant",
        content: cleanAnswer,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Save assistant message to database
      supabase
        .from('chat_messages')
        .insert({
          role: 'assistant',
          content: cleanAnswer,
        })
        .then(({ error }) => {
          if (error) console.error('Error saving assistant message:', error);
        });
    } catch (error) {
      toast.error("Failed to get response from AI");
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !isLoadingHistory && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
            <div className="gradient-primary p-4 rounded-2xl shadow-lg animate-pulse-glow">
              <Bot className="w-12 h-12 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-bold mb-2">How can I help you today?</h2>
              <p className="text-muted-foreground">
                Ask me anything about your uploaded documents
              </p>
            </div>
          </div>
        )}

        {isLoadingHistory && (
          <div className="flex items-center justify-center h-full">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
              <p className="text-muted-foreground">Loading chat history...</p>
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex gap-3 animate-fade-in ${
              message.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            {message.role === "assistant" && (
              <div className="gradient-primary p-2 rounded-lg h-fit shadow-md">
                <Bot className="w-5 h-5 text-white" />
              </div>
            )}

            <div
              className={`max-w-[80%] space-y-2 ${
                message.role === "user" ? "items-end" : "items-start"
              }`}
            >
              <Card
                className={`p-4 ${
                  message.role === "user"
                    ? "gradient-primary text-white shadow-lg"
                    : "glass border-0 shadow-lg"
                }`}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
              </Card>
            </div>

            {message.role === "user" && (
              <div className="bg-secondary p-2 rounded-lg h-fit shadow-md">
                <User className="w-5 h-5 text-white" />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3 animate-fade-in">
            <div className="gradient-primary p-2 rounded-lg h-fit shadow-md">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <Card className="glass border-0 p-4 shadow-lg">
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm text-muted-foreground">Thinking...</span>
              </div>
            </Card>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t glass">
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask a question..."
            disabled={isLoading}
            className="bg-background/50 border-primary/20 focus-visible:ring-primary"
          />
          <Button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="gradient-primary text-white shadow-lg hover:shadow-xl transition-all"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;