import { useState } from "react";
import { Upload, FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const API_BASE_URL = "http://localhost:8000";

interface UploadPanelProps {
  onUploadSuccess: () => void;
}

const UploadPanel = ({ onUploadSuccess }: UploadPanelProps) => {
  const [docId, setDocId] = useState("");
  const [pastedText, setPastedText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleUpload = async () => {
    if (!docId.trim()) {
      toast.error("Please enter a Document ID");
      return;
    }

    if (!file && !pastedText.trim()) {
      toast.error("Please either upload a file or paste text");
      return;
    }

    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append("doc_id", docId);

      if (file) {
        formData.append("file", file);
      } else {
        formData.append("text", pastedText);
      }

      const response = await fetch(`${API_BASE_URL}/ingest`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Upload failed");

      toast.success("Document uploaded successfully!");
      
      // Reset form
      setDocId("");
      setPastedText("");
      setFile(null);
      
      // Notify parent to refresh documents
      onUploadSuccess();
    } catch (error) {
      toast.error("Failed to upload document");
      console.error(error);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Card className="glass border-0 shadow-xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Upload className="w-5 h-5 text-primary" />
          Upload Document
        </CardTitle>
        <CardDescription>
          Add documents to your knowledge base
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="doc-id">Document ID</Label>
          <Input
            id="doc-id"
            placeholder="Enter unique document ID"
            value={docId}
            onChange={(e) => setDocId(e.target.value)}
            className="bg-background/50"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="paste-text">Paste Text</Label>
          <Textarea
            id="paste-text"
            placeholder="Paste your text here..."
            value={pastedText}
            onChange={(e) => setPastedText(e.target.value)}
            rows={6}
            className="bg-background/50 resize-none"
          />
        </div>

        <div className="relative">
          <div className="flex items-center justify-center w-full">
            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-xl cursor-pointer hover:bg-muted/50 transition-all">
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <FileText className="w-8 h-8 mb-2 text-muted-foreground" />
                <p className="mb-2 text-sm text-muted-foreground">
                  <span className="font-semibold">Click to upload</span> or drag and drop
                </p>
                <p className="text-xs text-muted-foreground">
                  CSV, TXT, or PDF files
                </p>
              </div>
              <input
                type="file"
                className="hidden"
                accept=".csv,.txt,.pdf"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>
          </div>
          {file && (
            <p className="mt-2 text-sm text-muted-foreground">
              Selected: {file.name}
            </p>
          )}
        </div>

        <Button
          onClick={handleUpload}
          disabled={isUploading}
          className="w-full gradient-primary text-white shadow-lg hover:shadow-xl transition-all"
        >
          {isUploading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Uploading...
            </>
          ) : (
            <>
              <Upload className="w-4 h-4 mr-2" />
              Upload Document
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
};

export default UploadPanel;
