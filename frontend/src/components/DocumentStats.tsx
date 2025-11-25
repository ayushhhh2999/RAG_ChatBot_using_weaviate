import { useEffect, useState } from "react";
import { FileText, RefreshCw, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

const API_BASE_URL = "http://localhost:8000";

interface DocumentStatsProps {
  refreshTrigger: number;
}

interface DocumentData {
  total_chunks: number;
  document_ids: string[];
}

const DocumentStats = ({ refreshTrigger }: DocumentStatsProps) => {
  const [documents, setDocuments] = useState<DocumentData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchDocuments = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/documents`);
      if (!response.ok) throw new Error("Failed to fetch documents");
      const data = await response.json();
      setDocuments(data);
    } catch (error) {
      toast.error("Failed to load documents");
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [refreshTrigger]);

  return (
    <Card className="glass border-0 shadow-xl">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-primary" />
            <CardTitle>Knowledge Base</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={fetchDocuments}
            disabled={isLoading}
            className="hover:bg-primary/10"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          </Button>
        </div>
        <CardDescription>Documents stored in memory</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between p-4 rounded-lg bg-gradient-to-r from-primary/10 to-secondary/10 border border-primary/20">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" />
            <span className="font-medium">Total Chunks</span>
          </div>
          <Badge variant="secondary" className="text-lg px-3 py-1">
            {documents?.total_chunks || 0}
          </Badge>
        </div>

        {documents?.document_ids && documents.document_ids.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-muted-foreground">Document IDs</h4>
            <div className="flex flex-wrap gap-2">
              {documents.document_ids.map((id, index) => (
                <Badge
                  key={index}
                  variant="outline"
                  className="bg-background/50 hover:bg-background transition-colors"
                >
                  {id}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {(!documents || documents.total_chunks === 0) && !isLoading && (
          <div className="text-center py-8 text-muted-foreground">
            <FileText className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No documents uploaded yet</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DocumentStats;
