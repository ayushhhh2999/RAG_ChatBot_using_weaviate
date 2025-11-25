import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { getDocuments, findCorruptedChunks, cleanDatabase } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { Database, AlertTriangle, ArrowLeft, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";

interface DocumentsResponse {
  total_chunks: number;
  ids_preview: string[];
}

interface CorruptedEntry {
  id: string;
  doc_preview: string;
  reasons?: string[];
}

interface CorruptedResponse {
  corrupted_count: number;
  corrupted_entries: CorruptedEntry[];
}

interface CleanResponse {
  status: string;
  deleted: number;
}

const DbInspector = () => {
  const [documents, setDocuments] = useState<DocumentsResponse | null>(null);
  const [corrupted, setCorrupted] = useState<CorruptedResponse | null>(null);
  const [cleanResult, setCleanResult] = useState<CleanResponse | null>(null);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);
  const [isLoadingCorrupted, setIsLoadingCorrupted] = useState(false);
  const [isLoadingClean, setIsLoadingClean] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    const loadDocuments = async () => {
      try {
        const data = await getDocuments();
        setDocuments(data);
      } catch (error) {
        console.error("Failed to load documents:", error);
      } finally {
        setIsLoadingDocs(false);
      }
    };

    loadDocuments();
  }, []);

  const handleFindCorrupted = async () => {
    setIsLoadingCorrupted(true);
    try {
      const data = await findCorruptedChunks();
      setCorrupted(data);
    } catch (error) {
      console.error("Failed to find corrupted chunks:", error);
    } finally {
      setIsLoadingCorrupted(false);
    }
  };

  const handleCleanDatabase = async () => {
    setIsLoadingClean(true);
    try {
      const data = await cleanDatabase();
      setCleanResult(data);
      toast({
        title: "Database Cleaned",
        description: `Successfully deleted ${data.deleted} corrupted entries`,
      });
      // Refresh documents after cleaning
      const updatedDocs = await getDocuments();
      setDocuments(updatedDocs);
    } catch (error) {
      console.error("Failed to clean database:", error);
      toast({
        title: "Error",
        description: "Failed to clean database",
        variant: "destructive",
      });
    } finally {
      setIsLoadingClean(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-primary/5 to-secondary/5">
      <Navbar />
      
      <div className="container mx-auto p-8 space-y-6 animate-fade-in">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <Database className="w-8 h-8 text-primary" />
            <h1 className="text-4xl font-bold gradient-text">Database Inspector</h1>
          </div>
          
          <Link to="/">
            <Button variant="outline" className="gap-2">
              <ArrowLeft className="w-4 h-4" />
              Back to Chat
            </Button>
          </Link>
        </div>

        {/* Database Summary Card */}
        <Card className="glass border-0 shadow-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="w-5 h-5" />
              Database Summary
            </CardTitle>
            <CardDescription>Overview of stored document chunks</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoadingDocs ? (
              <div className="text-muted-foreground">Loading...</div>
            ) : documents ? (
              <>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Total Chunks:</span>
                  <Badge variant="secondary" className="text-lg">
                    {documents.total_chunks}
                  </Badge>
                </div>

                <Separator />

                <div>
                  <h3 className="text-sm font-medium mb-3">ID Preview (First 10)</h3>
                  <ScrollArea className="h-[200px] rounded-md border p-4">
                    <div className="space-y-2">
                      {documents.ids_preview?.map((id, index) => (
                        <div key={index} className="flex items-center gap-2">
                          <Badge variant="outline" className="font-mono text-xs">
                            {index + 1}
                          </Badge>
                          <code className="text-xs text-muted-foreground">{id}</code>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </div>
              </>
            ) : (
              <div className="text-destructive">Failed to load documents</div>
            )}
          </CardContent>
        </Card>

        {/* Clean Database Card */}
        <Card className="glass border-0 shadow-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Trash2 className="w-5 h-5 text-destructive" />
              Clean Database
            </CardTitle>
            <CardDescription>Remove corrupted and malformed data entries</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button 
              onClick={handleCleanDatabase}
              disabled={isLoadingClean}
              variant="destructive"
              className="w-full sm:w-auto"
            >
              {isLoadingClean ? "Cleaning..." : "Clean Database"}
            </Button>

            {cleanResult && (
              <>
                <Separator />
                
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Deleted Entries:</span>
                  <Badge variant="secondary" className="text-lg">
                    {cleanResult.deleted}
                  </Badge>
                </div>
                
                {cleanResult.status === "ok" && (
                  <div className="text-sm text-muted-foreground">
                    Database cleanup completed successfully
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* Corrupted Chunks Card */}
        <Card className="glass border-0 shadow-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-destructive" />
              Corrupted Chunks
            </CardTitle>
            <CardDescription>Analyze and identify corrupted document chunks</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button 
              onClick={handleFindCorrupted}
              disabled={isLoadingCorrupted}
              className="w-full sm:w-auto"
            >
              {isLoadingCorrupted ? "Analyzing..." : "Find Corrupted Chunks"}
            </Button>

            {corrupted && (
              <>
                <Separator />
                
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Corrupted Count:</span>
                  <Badge 
                    variant={corrupted.corrupted_count > 0 ? "destructive" : "secondary"}
                    className="text-lg"
                  >
                    {corrupted.corrupted_count}
                  </Badge>
                </div>

                {corrupted.corrupted_entries?.length > 0 && (
                  <>
                    <Separator />
                    
                    <div>
                      <h3 className="text-sm font-medium mb-3">Corrupted Entries</h3>
                      <ScrollArea className="h-[400px] rounded-md border">
                        <div className="p-4 space-y-4">
                          {corrupted.corrupted_entries.map((entry, index) => (
                            <Card key={index} className="border-destructive/20">
                              <CardHeader className="pb-3">
                                <div className="flex items-center gap-2">
                                  <Badge variant="destructive">
                                    Entry {index + 1}
                                  </Badge>
                                  <code className="text-xs text-muted-foreground">
                                    {entry.id}
                                  </code>
                                </div>
                              </CardHeader>
                              <CardContent className="space-y-2">
                                <div>
                                  <span className="text-xs font-medium text-muted-foreground">
                                    Document Preview:
                                  </span>
                                  <p className="text-sm mt-1 p-2 bg-muted/50 rounded">
                                    {entry.doc_preview}
                                  </p>
                                </div>
                                
                                {entry.reasons && entry.reasons.length > 0 && (
                                  <div>
                                    <span className="text-xs font-medium text-muted-foreground">
                                      Reasons:
                                    </span>
                                    <ul className="list-disc list-inside text-sm mt-1 space-y-1">
                                      {entry.reasons.map((reason, i) => (
                                        <li key={i} className="text-destructive">
                                          {reason}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </CardContent>
                            </Card>
                          ))}
                        </div>
                      </ScrollArea>
                    </div>
                  </>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default DbInspector;
