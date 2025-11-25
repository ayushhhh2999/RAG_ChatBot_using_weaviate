import { useState } from "react";
import Navbar from "@/components/Navbar";
import UploadPanel from "@/components/UploadPanel";
import DocumentStats from "@/components/DocumentStats";
import ChatWindow from "@/components/ChatWindow";

const Index = () => {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleUploadSuccess = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-primary/5 to-secondary/5">
      <Navbar />
      
      <div className="container mx-auto p-4 h-[calc(100vh-4rem)]">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-full">
          {/* Left Panel - Upload & Stats */}
          <div className="lg:col-span-1 space-y-4 overflow-y-auto">
            <UploadPanel onUploadSuccess={handleUploadSuccess} />
            <DocumentStats refreshTrigger={refreshTrigger} />
          </div>

          {/* Right Panel - Chat */}
          <div className="lg:col-span-2 glass rounded-2xl border-0 shadow-2xl overflow-hidden">
            <ChatWindow />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Index;
