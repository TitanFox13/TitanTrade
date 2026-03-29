import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../models/cost_record.dart';
import '../models/portfolio.dart';
import '../models/trade.dart';
import '../providers/costs_provider.dart';
import '../providers/portfolio_provider.dart';
import '../providers/trade_log_provider.dart';
import '../theme.dart';
import '../widgets/pnl_chip.dart';

// ---------------------------------------------------------------------------
// Realized P&L helper: match BUY->SELL round-trips per ticker
// ---------------------------------------------------------------------------

class RoundTrip {
  final String ticker;
  final Trade buy;
  final Trade sell;

  RoundTrip({required this.ticker, required this.buy, required this.sell});

  double get realizedPnl => (sell.price - buy.price) * sell.shares;
  double get realizedPnlPercent =>
      buy.price > 0 ? ((sell.price - buy.price) / buy.price) * 100 : 0;
  Duration get holdDuration => sell.timestamp.difference(buy.timestamp);
}

List<RoundTrip> _buildRoundTrips(List<Trade> trades) {
  // Chronological order for matching
  final sorted = [...trades]..sort((a, b) => a.timestamp.compareTo(b.timestamp));

  // For each ticker, maintain a queue of unmatched BUYs
  final openBuys = <String, List<Trade>>{};
  final trips = <RoundTrip>[];

  for (final t in sorted) {
    if (t.isBuy) {
      openBuys.putIfAbsent(t.ticker, () => []).add(t);
    } else {
      // SELL - match against earliest open BUY for this ticker
      final buys = openBuys[t.ticker];
      if (buys != null && buys.isNotEmpty) {
        final buy = buys.removeAt(0);
        trips.add(RoundTrip(ticker: t.ticker, buy: buy, sell: t));
      }
    }
  }

  // Most recent first
  trips.sort((a, b) => b.sell.timestamp.compareTo(a.sell.timestamp));
  return trips;
}

// ---------------------------------------------------------------------------
// Cost summary helpers
// ---------------------------------------------------------------------------

class _ServiceSummary {
  final String service;
  int calls = 0;
  int inputTokens = 0;
  int outputTokens = 0;
  double totalCost = 0;

  _ServiceSummary(this.service);
}

Map<String, _ServiceSummary> _summarizeCosts(List<CostRecord> costs) {
  final map = <String, _ServiceSummary>{};
  for (final c in costs) {
    final s = map.putIfAbsent(c.service, () => _ServiceSummary(c.service));
    s.calls++;
    s.inputTokens += c.inputTokens;
    s.outputTokens += c.outputTokens;
    s.totalCost += c.estimatedCostUsd;
  }
  return map;
}

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

class StatisticsScreen extends ConsumerWidget {
  const StatisticsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final portfolioAsync = ref.watch(portfolioProvider);
    final tradesAsync = ref.watch(tradeLogProvider);
    final costsAsync = ref.watch(costsProvider);

    final portfolio = portfolioAsync.valueOrNull ?? Portfolio.empty;
    final trades = tradesAsync.valueOrNull ?? [];
    final costs = costsAsync.valueOrNull ?? [];

    final roundTrips = _buildRoundTrips(trades);
    final totalRealizedPnl =
        roundTrips.fold(0.0, (sum, rt) => sum + rt.realizedPnl);
    final totalUnrealizedPnl = portfolio.totalUnrealizedPnl;
    final totalTradingPnl = totalRealizedPnl + totalUnrealizedPnl;
    final totalCosts = costs.fold(0.0, (sum, c) => sum + c.estimatedCostUsd);
    final netPnl = totalTradingPnl - totalCosts;

    final theme = Theme.of(context);

    return Scaffold(
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text('Statistics', style: theme.textTheme.headlineMedium),
          const SizedBox(height: 20),

          // ---- Net P&L summary ----
          _NetSummaryCard(
            totalRealizedPnl: totalRealizedPnl,
            totalUnrealizedPnl: totalUnrealizedPnl,
            totalCosts: totalCosts,
            netPnl: netPnl,
          ),
          const SizedBox(height: 24),

          // ---- Open positions P&L ----
          Text('Open Positions', style: theme.textTheme.titleLarge),
          const SizedBox(height: 8),
          if (portfolio.positions.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: Text('No open positions'),
              ),
            )
          else
            ...portfolio.positions.map((p) => _PositionPnlTile(position: p)),
          const SizedBox(height: 24),

          // ---- Realized trades P&L ----
          Text('Closed Trades', style: theme.textTheme.titleLarge),
          const SizedBox(height: 8),
          if (roundTrips.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: Text('No completed round-trips yet'),
              ),
            )
          else
            ...roundTrips.map((rt) => _RoundTripTile(roundTrip: rt)),
          const SizedBox(height: 24),

          // ---- Operational costs ----
          Text('Operational Costs', style: theme.textTheme.titleLarge),
          const SizedBox(height: 8),
          _CostSummaryCard(costs: costs),
          if (costs.isNotEmpty) ...[
            const SizedBox(height: 12),
            _RecentCostsList(costs: costs),
          ],
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Net summary card
// ---------------------------------------------------------------------------

class _NetSummaryCard extends StatelessWidget {
  final double totalRealizedPnl;
  final double totalUnrealizedPnl;
  final double totalCosts;
  final double netPnl;

  const _NetSummaryCard({
    required this.totalRealizedPnl,
    required this.totalUnrealizedPnl,
    required this.totalCosts,
    required this.netPnl,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            _StatCol(
              label: 'Net P&L',
              titleStyle: theme.textTheme.headlineSmall!.merge(monoStyle),
              child: PnlChip(value: netPnl),
            ),
            const SizedBox(width: 40),
            _StatCol(
              label: 'Realized P&L',
              child: PnlChip(value: totalRealizedPnl),
            ),
            const SizedBox(width: 40),
            _StatCol(
              label: 'Unrealized P&L',
              child: PnlChip(value: totalUnrealizedPnl),
            ),
            const SizedBox(width: 40),
            _StatCol(
              label: 'Operational Costs',
              child: Text(
                '-\$${totalCosts.toStringAsFixed(2)}',
                style: monoStyle.copyWith(
                  color: totalCosts > 0 ? const Color(0xFFEF5350) : null,
                  fontSize: 13,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatCol extends StatelessWidget {
  final String label;
  final Widget child;
  final TextStyle? titleStyle;

  const _StatCol({required this.label, required this.child, this.titleStyle});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 4),
        child,
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Position P&L tile
// ---------------------------------------------------------------------------

class _PositionPnlTile extends StatelessWidget {
  final Position position;

  const _PositionPnlTile({required this.position});

  @override
  Widget build(BuildContext context) {
    final pnl = position.unrealizedPnl ?? (position.marketValue - position.costBasis);
    final pnlPct = position.pnlPercent;

    return Card(
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: pnlColor(pnl).withValues(alpha: 0.2),
          child: Text(
            position.ticker.substring(0, position.ticker.length.clamp(0, 2)),
            style: TextStyle(color: pnlColor(pnl), fontWeight: FontWeight.bold),
          ),
        ),
        title: Text('${position.ticker}  ${position.shares} shares'),
        subtitle: Text(
          'Entry \$${position.entryPrice.toStringAsFixed(2)}  '
          'Current \$${(position.currentPrice ?? position.entryPrice).toStringAsFixed(2)}',
          style: monoStyle.copyWith(fontSize: 12),
        ),
        trailing: PnlChip(value: pnl, percent: pnlPct),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Round-trip tile
// ---------------------------------------------------------------------------

class _RoundTripTile extends StatelessWidget {
  final RoundTrip roundTrip;

  const _RoundTripTile({required this.roundTrip});

  @override
  Widget build(BuildContext context) {
    final pnl = roundTrip.realizedPnl;
    final pct = roundTrip.realizedPnlPercent;
    final days = roundTrip.holdDuration.inDays;
    final dateFmt = DateFormat('MMM d');

    return Card(
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: pnlColor(pnl).withValues(alpha: 0.2),
          child: Text(
            roundTrip.ticker.substring(0, roundTrip.ticker.length.clamp(0, 2)),
            style: TextStyle(color: pnlColor(pnl), fontWeight: FontWeight.bold),
          ),
        ),
        title: Text(
          '${roundTrip.ticker}  ${roundTrip.sell.shares} shares  '
          '(${days}d hold)',
        ),
        subtitle: Text(
          'Buy \$${roundTrip.buy.price.toStringAsFixed(2)} '
          '${dateFmt.format(roundTrip.buy.timestamp)}  '
          'Sell \$${roundTrip.sell.price.toStringAsFixed(2)} '
          '${dateFmt.format(roundTrip.sell.timestamp)}  '
          '(${roundTrip.sell.trigger})',
          style: monoStyle.copyWith(fontSize: 12),
        ),
        trailing: PnlChip(value: pnl, percent: pct),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Cost summary card
// ---------------------------------------------------------------------------

class _CostSummaryCard extends StatelessWidget {
  final List<CostRecord> costs;

  const _CostSummaryCard({required this.costs});

  @override
  Widget build(BuildContext context) {
    if (costs.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Text('No operational costs recorded yet'),
        ),
      );
    }

    final summaries = _summarizeCosts(costs);
    final totalCost = costs.fold(0.0, (sum, c) => sum + c.estimatedCostUsd);
    final totalTokens = costs.fold(0, (sum, c) => sum + c.totalTokens);
    final theme = Theme.of(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  'Total: \$${totalCost.toStringAsFixed(4)}',
                  style: theme.textTheme.titleMedium!.merge(monoStyle),
                ),
                const SizedBox(width: 24),
                Text(
                  '${costs.length} API calls  |  '
                  '${_formatTokens(totalTokens)} tokens',
                  style: theme.textTheme.bodySmall,
                ),
              ],
            ),
            const Divider(height: 24),
            ...summaries.values.map((s) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 80,
                        child: Text(
                          s.service.toUpperCase(),
                          style: theme.textTheme.labelMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      Text(
                        '\$${s.totalCost.toStringAsFixed(4)}',
                        style: monoStyle.copyWith(fontSize: 13),
                      ),
                      const SizedBox(width: 16),
                      Text(
                        '${s.calls} calls  |  '
                        '${_formatTokens(s.inputTokens)} in  |  '
                        '${_formatTokens(s.outputTokens)} out',
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ),
                )),
          ],
        ),
      ),
    );
  }
}

String _formatTokens(int tokens) {
  if (tokens >= 1000000) return '${(tokens / 1000000).toStringAsFixed(1)}M';
  if (tokens >= 1000) return '${(tokens / 1000).toStringAsFixed(1)}K';
  return '$tokens';
}

// ---------------------------------------------------------------------------
// Recent costs list (last 20)
// ---------------------------------------------------------------------------

class _RecentCostsList extends StatelessWidget {
  final List<CostRecord> costs;

  const _RecentCostsList({required this.costs});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final recent = costs.take(20).toList();
    final dateFmt = DateFormat('MMM d HH:mm');

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Recent API Calls', style: theme.textTheme.titleSmall),
            const SizedBox(height: 8),
            ...recent.map((c) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 110,
                        child: Text(
                          dateFmt.format(c.timestamp.toLocal()),
                          style: theme.textTheme.bodySmall,
                        ),
                      ),
                      SizedBox(
                        width: 70,
                        child: Text(
                          c.service,
                          style: theme.textTheme.labelSmall?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      Expanded(
                        child: Text(
                          c.description,
                          style: theme.textTheme.bodySmall,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        '\$${c.estimatedCostUsd.toStringAsFixed(4)}',
                        style: monoStyle.copyWith(fontSize: 12),
                      ),
                    ],
                  ),
                )),
          ],
        ),
      ),
    );
  }
}
