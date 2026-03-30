import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/portfolio_provider.dart';
import '../providers/sentry_provider.dart';
import '../providers/trade_log_provider.dart';
import '../providers/trailing_stops_provider.dart';
import '../widgets/portfolio_summary_card.dart';
import '../widgets/position_tile.dart';
import '../widgets/sentry_badge.dart';
import '../widgets/trade_tile.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final portfolio = ref.watch(portfolioProvider);
    final trades = ref.watch(tradeLogProvider);
    final sentry = ref.watch(sentryProvider);
    final trailingStops = ref.watch(trailingStopsProvider);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: ListView(
        children: [
          Text('Dashboard', style: theme.textTheme.headlineSmall),
          const SizedBox(height: 16),

          // Portfolio summary
          portfolio.when(
            loading: () => const Card(child: Padding(padding: EdgeInsets.all(20), child: CircularProgressIndicator())),
            error: (e, st) => Card(child: Padding(padding: const EdgeInsets.all(20), child: Text('Error: $e'))),
            data: (p) => PortfolioSummaryCard(portfolio: p),
          ),
          const SizedBox(height: 24),

          // Active positions
          Text('Active Positions', style: theme.textTheme.titleMedium),
          const SizedBox(height: 8),
          portfolio.when(
            loading: () => const SizedBox.shrink(),
            error: (e, st) => const SizedBox.shrink(),
            data: (p) {
              final tsMap = trailingStops.valueOrNull ?? {};
              return p.positions.isEmpty
                  ? const Card(child: Padding(padding: EdgeInsets.all(20), child: Text('No open positions.')))
                  : Column(
                      children: p.positions
                          .map((pos) => PositionTile(
                                position: pos,
                                trailingStop: tsMap[pos.ticker],
                              ))
                          .toList(),
                    );
            },
          ),
          const SizedBox(height: 24),

          // Latest sentry signals
          Text('Latest Sentry Signals', style: theme.textTheme.titleMedium),
          const SizedBox(height: 8),
          sentry.when(
            loading: () => const SizedBox.shrink(),
            error: (e, st) => const SizedBox.shrink(),
            data: (bundle) => bundle == null
                ? const Card(child: Padding(padding: EdgeInsets.all(20), child: Text('No sentry data yet.')))
                : Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Run: ${bundle.runType}', style: theme.textTheme.bodySmall),
                          const SizedBox(height: 8),
                          ...bundle.signals.map(
                            (s) => Padding(
                              padding: const EdgeInsets.only(bottom: 8),
                              child: Row(
                                children: [
                                  SizedBox(
                                    width: 60,
                                    child: Text(s.ticker, style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold)),
                                  ),
                                  SentryBadge(signal: s.signal),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: Text(s.reasoning, style: theme.textTheme.bodySmall, overflow: TextOverflow.ellipsis),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
          ),
          const SizedBox(height: 24),

          // Recent trades
          Row(
            children: [
              Text('Recent Trades', style: theme.textTheme.titleMedium),
              const Spacer(),
              TextButton(onPressed: () => context.go('/trades'), child: const Text('View all')),
            ],
          ),
          const SizedBox(height: 8),
          trades.when(
            loading: () => const SizedBox.shrink(),
            error: (e, st) => const SizedBox.shrink(),
            data: (list) => list.isEmpty
                ? const Card(child: Padding(padding: EdgeInsets.all(20), child: Text('No trades yet.')))
                : Column(
                    children: list
                        .take(5)
                        .toList()
                        .asMap()
                        .entries
                        .map((e) => TradeTile(
                              trade: e.value,
                              onTap: () => context.go('/trades/${e.key}'),
                            ))
                        .toList(),
                  ),
          ),
        ],
      ),
    );
  }
}
