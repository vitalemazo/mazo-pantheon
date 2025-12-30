import { useEffect } from 'react';
import { Layout } from './components/Layout';
import { Toaster } from './components/ui/sonner';
import { initializeDataHydration, useDataStore } from './services/data-hydration-service';
import { Loader2 } from 'lucide-react';

// Global operations indicator - shows when AI is processing
function GlobalOperationsIndicator() {
  const activeOperations = useDataStore((state) => state.activeOperations);
  const ops = Object.entries(activeOperations);
  
  if (ops.length === 0) return null;
  
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {ops.map(([id, op]) => (
        <div 
          key={id}
          className="flex items-center gap-2 px-3 py-2 bg-slate-800/95 border border-cyan-500/50 rounded-lg shadow-lg backdrop-blur-sm animate-in slide-in-from-right"
        >
          <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
          <span className="text-sm text-slate-200">{op.message}</span>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  // Initialize data hydration once on app startup
  useEffect(() => {
    initializeDataHydration();
  }, []);

  return (
    <>
      <Layout>
        {/* Main content is handled by TabContent inside Layout */}
        <></>
      </Layout>
      <Toaster />
      <GlobalOperationsIndicator />
    </>
  );
}
