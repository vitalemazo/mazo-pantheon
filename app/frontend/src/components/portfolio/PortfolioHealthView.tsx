import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { usePortfolioHealth } from '@/contexts/portfolio-health-context';
import { 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  AlertTriangle, 
  CheckCircle, 
  XCircle,
  DollarSign,
  PieChart,
  Activity,
  Shield,
  Target,
  Zap
} from 'lucide-react';

function getGradeColor(grade: string): string {
  if (grade.startsWith('A')) return 'text-emerald-400';
  if (grade.startsWith('B')) return 'text-green-400';
  if (grade.startsWith('C')) return 'text-yellow-400';
  if (grade.startsWith('D')) return 'text-orange-400';
  return 'text-red-400';
}

function getGradeBg(grade: string): string {
  if (grade.startsWith('A')) return 'bg-emerald-500/20 border-emerald-500/50';
  if (grade.startsWith('B')) return 'bg-green-500/20 border-green-500/50';
  if (grade.startsWith('C')) return 'bg-yellow-500/20 border-yellow-500/50';
  if (grade.startsWith('D')) return 'bg-orange-500/20 border-orange-500/50';
  return 'bg-red-500/20 border-red-500/50';
}

function extractGrade(analysis: string): string {
  const gradeMatch = analysis.match(/GRADE:\s*([A-F][+-]?)/i) || 
                     analysis.match(/Grade:\s*([A-F][+-]?)/i) ||
                     analysis.match(/receives a grade of\s*([A-F][+-]?)/i);
  return gradeMatch ? gradeMatch[1] : '?';
}

function extractRiskLevel(analysis: string): string {
  if (analysis.toLowerCase().includes('critical')) return 'CRITICAL';
  if (analysis.toLowerCase().includes('high risk')) return 'HIGH';
  if (analysis.toLowerCase().includes('moderate')) return 'MODERATE';
  if (analysis.toLowerCase().includes('low risk')) return 'LOW';
  return 'UNKNOWN';
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

export function PortfolioHealthView() {
  // Use the context - data persists across tab switches!
  const { 
    healthData, 
    loading, 
    error, 
    lastRefresh, 
    runHealthCheck 
  } = usePortfolioHealth();

  // Only auto-run if we don't have cached data
  useEffect(() => {
    if (!healthData && !loading) {
      runHealthCheck();
    }
  }, []); // Empty deps - only run once on initial mount if no data

  const grade = healthData ? extractGrade(healthData.analysis) : '?';
  const riskLevel = healthData ? extractRiskLevel(healthData.analysis) : 'UNKNOWN';

  return (
    <div className="h-full overflow-auto bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
              Portfolio Health Center
            </h1>
            <p className="text-slate-400 mt-1">
              Powered by Mazo AI • Real-time portfolio analysis and recommendations
            </p>
          </div>
          <div className="flex items-center gap-4">
            {lastRefresh && (
              <span className="text-xs text-slate-500">
                Last updated: {lastRefresh.toLocaleTimeString()}
                {/* Show how long ago the data was fetched */}
                <span className="ml-2 text-slate-600">
                  (cached - click refresh to update)
                </span>
              </span>
            )}
            <Button 
              onClick={runHealthCheck} 
              disabled={loading}
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              {loading ? 'Analyzing...' : 'Run Health Check'}
            </Button>
          </div>
        </div>

        {error && (
          <Card className="border-red-500/50 bg-red-500/10">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3 text-red-400">
                <XCircle className="w-5 h-5" />
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {loading && !healthData && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <Card key={i} className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <Skeleton className="h-4 w-24" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-8 w-32" />
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {healthData && (
          <>
            {/* Portfolio Overview Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Grade Card */}
              <Card className={`${getGradeBg(grade)} border`}>
                <CardHeader className="pb-2">
                  <CardDescription className="text-slate-300 flex items-center gap-2">
                    <Shield className="w-4 h-4" />
                    Health Grade
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className={`text-5xl font-black ${getGradeColor(grade)}`}>
                    {grade}
                  </div>
                  <Badge 
                    variant="outline" 
                    className={`mt-2 ${
                      riskLevel === 'CRITICAL' ? 'border-red-500 text-red-400' :
                      riskLevel === 'HIGH' ? 'border-orange-500 text-orange-400' :
                      riskLevel === 'MODERATE' ? 'border-yellow-500 text-yellow-400' :
                      'border-green-500 text-green-400'
                    }`}
                  >
                    {riskLevel} RISK
                  </Badge>
                </CardContent>
              </Card>

              {/* Equity Card */}
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader className="pb-2">
                  <CardDescription className="text-slate-400 flex items-center gap-2">
                    <DollarSign className="w-4 h-4" />
                    Total Equity
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-white">
                    {formatCurrency(healthData.portfolio.equity)}
                  </div>
                  <div className="text-sm text-slate-400 mt-1">
                    Buying Power: {formatCurrency(healthData.portfolio.buying_power)}
                  </div>
                </CardContent>
              </Card>

              {/* Cash Card */}
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader className="pb-2">
                  <CardDescription className="text-slate-400 flex items-center gap-2">
                    <PieChart className="w-4 h-4" />
                    Available Cash
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-emerald-400">
                    {formatCurrency(healthData.portfolio.cash)}
                  </div>
                  <div className="text-sm text-slate-400 mt-1">
                    {((healthData.portfolio.cash / healthData.portfolio.equity) * 100).toFixed(1)}% of equity
                  </div>
                </CardContent>
              </Card>

              {/* Analysis Confidence */}
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader className="pb-2">
                  <CardDescription className="text-slate-400 flex items-center gap-2">
                    <Target className="w-4 h-4" />
                    Analysis Confidence
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-purple-400">
                    {((healthData.confidence || 0) * 100).toFixed(0)}%
                  </div>
                  <div className="text-sm text-slate-400 mt-1">
                    Execution: {(healthData.execution_time_ms / 1000).toFixed(1)}s
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Positions Table */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <Activity className="w-5 h-5 text-blue-400" />
                  Current Positions
                </CardTitle>
                <CardDescription>
                  {healthData.positions.length} active position{healthData.positions.length !== 1 ? 's' : ''}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {healthData.positions.length === 0 ? (
                  <div className="text-center py-8 text-slate-400">
                    <PieChart className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>No open positions</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-slate-700">
                          <th className="text-left py-3 px-4 text-slate-400 font-medium">Symbol</th>
                          <th className="text-right py-3 px-4 text-slate-400 font-medium">Quantity</th>
                          <th className="text-right py-3 px-4 text-slate-400 font-medium">Entry Price</th>
                          <th className="text-right py-3 px-4 text-slate-400 font-medium">Current Price</th>
                          <th className="text-right py-3 px-4 text-slate-400 font-medium">Market Value</th>
                          <th className="text-right py-3 px-4 text-slate-400 font-medium">P&L</th>
                          <th className="text-right py-3 px-4 text-slate-400 font-medium">% of Portfolio</th>
                        </tr>
                      </thead>
                      <tbody>
                        {healthData.positions.map((pos) => {
                          const isShort = pos.qty < 0;
                          const isProfit = pos.unrealized_pl > 0;
                          const concentration = Math.abs(pos.market_value) / healthData.portfolio.equity * 100;
                          const isOverConcentrated = concentration > 25;
                          
                          return (
                            <tr key={pos.symbol} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                              <td className="py-3 px-4">
                                <div className="flex items-center gap-2">
                                  <span className="font-semibold text-white">{pos.symbol}</span>
                                  <Badge variant="outline" className={isShort ? 'border-red-500 text-red-400' : 'border-green-500 text-green-400'}>
                                    {isShort ? 'SHORT' : 'LONG'}
                                  </Badge>
                                </div>
                              </td>
                              <td className="text-right py-3 px-4 text-white font-mono">
                                {Math.abs(pos.qty)}
                              </td>
                              <td className="text-right py-3 px-4 text-slate-300 font-mono">
                                {formatCurrency(pos.avg_entry_price)}
                              </td>
                              <td className="text-right py-3 px-4 text-white font-mono">
                                {formatCurrency(pos.current_price)}
                              </td>
                              <td className="text-right py-3 px-4 text-slate-300 font-mono">
                                {formatCurrency(Math.abs(pos.market_value))}
                              </td>
                              <td className="text-right py-3 px-4">
                                <div className={`flex items-center justify-end gap-1 font-mono ${isProfit ? 'text-emerald-400' : 'text-red-400'}`}>
                                  {isProfit ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                                  <span>{formatCurrency(pos.unrealized_pl)}</span>
                                  <span className="text-xs">({formatPercent(pos.unrealized_plpc)})</span>
                                </div>
                              </td>
                              <td className="text-right py-3 px-4">
                                <div className="flex items-center justify-end gap-2">
                                  <span className={`font-mono ${isOverConcentrated ? 'text-orange-400' : 'text-slate-300'}`}>
                                    {concentration.toFixed(1)}%
                                  </span>
                                  {isOverConcentrated && (
                                    <AlertTriangle className="w-4 h-4 text-orange-400" />
                                  )}
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Pending Orders */}
            {healthData.pending_orders.length > 0 && (
              <Card className="bg-slate-800/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Zap className="w-5 h-5 text-yellow-400" />
                    Pending Orders
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {healthData.pending_orders.map((order) => (
                      <div 
                        key={order.id}
                        className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg"
                      >
                        <div className="flex items-center gap-3">
                          <Badge className={order.side === 'buy' ? 'bg-green-600' : 'bg-red-600'}>
                            {order.side.toUpperCase()}
                          </Badge>
                          <span className="font-semibold text-white">{order.symbol}</span>
                          <span className="text-slate-400">{order.qty} shares</span>
                        </div>
                        <Badge variant="outline" className="border-yellow-500 text-yellow-400">
                          {order.status}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Mazo Analysis */}
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <CheckCircle className="w-5 h-5 text-purple-400" />
                  Mazo AI Analysis & Recommendations
                </CardTitle>
                <CardDescription>
                  Comprehensive portfolio health analysis with actionable recommendations
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="prose prose-invert max-w-none">
                  <pre className="whitespace-pre-wrap text-sm text-slate-300 font-sans leading-relaxed bg-slate-900/50 p-6 rounded-lg overflow-auto max-h-[600px]">
                    {healthData.analysis}
                  </pre>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
