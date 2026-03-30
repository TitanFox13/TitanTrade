import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../models/trade.dart';
import '../providers/sentry_provider.dart';
import '../providers/thesis_provider.dart';
import '../providers/trade_log_provider.dart';
import '../theme.dart';
import '../widgets/context_card.dart';
import '../widgets/gate_result_tile.dart';
import '../widgets/sentry_badge.dart';

class TradeDetailScreen extends ConsumerWidget {
  final int tradeIndex;

  const TradeDetailScreen({super.key, required this.tradeIndex});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final trades = ref.watch(tradeLogProvider);
    final thesisBundle = ref.watch(thesisProvider);
    final sentryBundle = ref.watch(sentryProvider);

    return trades.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
      data: (list) {
        if (tradeIndex >= list.length) {
          return const Center(child: Text('Trade not found.'));
        }

        final trade = list[tradeIndex];
        final dateStr = DateFormat('yyyy-MM-dd HH:mm:ss').format(trade.timestamp.toLocal());

        // Find matching thesis
        final thesis = thesisBundle.valueOrNull?.theses
            .where((t) => t.ticker == trade.ticker)
            .firstOrNull;

        // Find matching sentry signal
        final sentrySignal = sentryBundle.valueOrNull?.signals
            .where((s) => s.ticker == trade.ticker)
            .firstOrNull;

        return Padding(
          padding: const EdgeInsets.all(24),
          child: ListView(
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () => context.canPop() ? context.pop() : context.go('/trades'),
                  icon: const Icon(Icons.arrow_back),
                  label: const Text('Back'),
                ),
              ),
              const SizedBox(height: 8),

              _TradeHeader(trade: trade, dateStr: dateStr),
              const SizedBox(height: 24),

              // Market & technical context (from trade record)
              if (trade.context != null) ...[
                _SectionHeader(title: 'Market & Technical Context'),
                const SizedBox(height: 8),
                TradeContextCard(context: trade.context!),
                const SizedBox(height: 24),
              ],

              // Risk gate results (from trade record)
              if (trade.gateResults.isNotEmpty) ...[
                _SectionHeader(title: 'Risk Gate Results'),
                const SizedBox(height: 8),
                GateResultsCard(gateResults: trade.gateResults),
                const SizedBox(height: 24),
              ],

              // Thesis context
              _SectionHeader(title: 'Thesis Context'),
              const SizedBox(height: 8),
              if (thesis != null)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text('${thesis.thesis} (${thesis.confidencePercent}% confidence)',
                                style: theme.textTheme.titleSmall),
                            if (thesis.selectedForTrading) ...[
                              const SizedBox(width: 8),
                              const Chip(label: Text('Selected'), visualDensity: VisualDensity.compact),
                            ],
                          ],
                        ),
                        const SizedBox(height: 8),
                        if (thesis.targetEntryPrice != null)
                          Text('Entry: \$${thesis.targetEntryPrice!.toStringAsFixed(2)}  |  '
                              'Stop: \$${thesis.stopLossPrice?.toStringAsFixed(2) ?? "N/A"}  |  '
                              'Target: \$${thesis.takeProfitPrice?.toStringAsFixed(2) ?? "N/A"}',
                              style: monoStyle.copyWith(fontSize: 13)),
                        const SizedBox(height: 8),
                        Text('Breach condition: ${thesis.thesisBreachCondition}',
                            style: theme.textTheme.bodySmall?.copyWith(color: Colors.orange)),
                        const SizedBox(height: 12),
                        Text(thesis.reasoning, style: theme.textTheme.bodyMedium),
                      ],
                    ),
                  ),
                )
              else
                const Card(child: Padding(padding: EdgeInsets.all(16), child: Text('No matching thesis found.'))),
              const SizedBox(height: 24),

              // Sentry context
              _SectionHeader(title: 'Sentry Context'),
              const SizedBox(height: 8),
              if (sentrySignal != null)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SentryBadge(signal: sentrySignal.signal),
                        const SizedBox(height: 8),
                        Text(sentrySignal.reasoning, style: theme.textTheme.bodyMedium),
                        if (sentrySignal.conflictingHeadlines.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Text('Conflicting headlines:', style: theme.textTheme.bodySmall),
                          ...sentrySignal.conflictingHeadlines
                              .map((h) => Padding(
                                    padding: const EdgeInsets.only(left: 12, top: 4),
                                    child: Text('- $h', style: theme.textTheme.bodySmall),
                                  )),
                        ],
                      ],
                    ),
                  ),
                )
              else
                const Card(child: Padding(padding: EdgeInsets.all(16), child: Text('No matching sentry signal.'))),
              const SizedBox(height: 24),

              // Execution details
              _SectionHeader(title: 'Execution Details'),
              const SizedBox(height: 8),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Trigger: ${trade.trigger}', style: theme.textTheme.bodyMedium),
                      const SizedBox(height: 4),
                      Text('Total value: \$${trade.totalValue.toStringAsFixed(2)}',
                          style: theme.textTheme.bodyMedium?.merge(monoStyle)),
                      if (trade.confidence != null) ...[
                        const SizedBox(height: 4),
                        Text('Confidence: ${(trade.confidence! * 100).round()}%',
                            style: theme.textTheme.bodyMedium),
                      ],
                      if (trade.riskFlags.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Text('Risk flags:', style: theme.textTheme.bodySmall?.copyWith(color: Colors.orange)),
                        ...trade.riskFlags.map((f) => Text('  - $f', style: theme.textTheme.bodySmall)),
                      ],
                      if (trade.reasoning.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Text(trade.reasoning, style: theme.textTheme.bodyMedium),
                      ],
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _TradeHeader extends StatelessWidget {
  final Trade trade;
  final String dateStr;

  const _TradeHeader({required this.trade, required this.dateStr});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final actionColor = trade.isBuy ? Colors.green : Colors.red;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Text(trade.ticker, style: theme.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold)),
        const SizedBox(width: 12),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: actionColor.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(trade.action, style: TextStyle(color: actionColor, fontWeight: FontWeight.bold)),
        ),
        const SizedBox(width: 12),
        Text(
          '${trade.shares} shares @ \$${trade.price.toStringAsFixed(2)}',
          style: theme.textTheme.titleMedium?.merge(monoStyle),
        ),
        const Spacer(),
        Text(dateStr, style: theme.textTheme.bodySmall),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;

  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold));
  }
}
