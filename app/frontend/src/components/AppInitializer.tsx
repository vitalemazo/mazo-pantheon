/**
 * App Initializer
 * 
 * This component runs ONCE when the app loads and:
 * 1. Hydrates all data from the backend
 * 2. Starts background refresh
 * 
 * After this runs, all components have access to cached data
 * and never need to show loading states (except for truly new operations).
 */

import { useEffect, useState } from 'react';
import { dataHydrationService, useDataStore } from '@/services/data-hydration-service';

interface Props {
  children: React.ReactNode;
}

export function AppInitializer({ children }: Props) {
  const [isReady, setIsReady] = useState(false);
  const isInitialized = useDataStore((state) => state.isInitialized);

  useEffect(() => {
    async function init() {
      // Hydrate all data on startup
      await dataHydrationService.hydrateAll();
      
      // Start background refresh (every 15 seconds)
      dataHydrationService.startBackgroundRefresh(15000);
      
      setIsReady(true);
    }

    init();

    // Cleanup on unmount
    return () => {
      dataHydrationService.stopBackgroundRefresh();
    };
  }, []);

  // Show a brief loading screen only on first load
  // This is the ONLY time the user sees a loading state
  if (!isReady && !isInitialized) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-slate-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-amber-500 mx-auto mb-4"></div>
          <h1 className="text-xl font-semibold text-white mb-2">Mazo Pantheon</h1>
          <p className="text-slate-400">Initializing autonomous trading system...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
