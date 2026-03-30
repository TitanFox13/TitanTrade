import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/sentry_provider.dart';
import '../providers/thesis_provider.dart';
import '../theme.dart';
import '../widgets/sentry_badge.dart';

class ThesisDetailScreen extends ConsumerWidget {
  final String ticker;

  const ThesisDetailScreen({super.key, required this.ticker});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final bundle = ref.watch(thesisProvider);
    final sentryBundle = ref.watch(sentryProvider);

    return bundle.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
      data: (b) {
        final thesis = b?.theses.where((t) => t.ticker == ticker).firstOrNull;
        if (thesis == null) {
          return const Center(child: Text('Thesis not found.'));
        }

        final sentrySignal = sentryBundle.valueOrNull?.signals
            .where((s) => s.ticker == ticker)
            .firstOrNull;

        final thesisColor = switch (thesis.thesis) {
          'BULLISH' => Colors.green,
          'BEARISH' => Colors.red,
          _ => Colors.grey,
        };

        return Padding(
          padding: const EdgeInsets.all(24),
          child: ListView(
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () => context.canPop() ? context.pop() : context.go('/theses'),
                  icon: const Icon(Icons.arrow_back),
                  label: const Text('Back'),
                ),
              ),
              const SizedBox(height: 8),

              // Header
              Row(
                children: [
                  Text(ticker, style: theme.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(width: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: thesisColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(thesis.thesis, style: TextStyle(color: thesisColor, fontWeight: FontWeight.bold)),
                  ),
                  const SizedBox(width: 12),
                  Text('${thesis.confidencePercent}% confidence', style: theme.textTheme.titleMedium),
                  if (thesis.sector != null) ...[
                    const SizedBox(width: 12),
                    Chip(label: Text(thesis.sector!), visualDensity: VisualDensity.compact),
                  ],
                  if (thesis.selectedForTrading) ...[
                    const SizedBox(width: 8),
                    const Chip(
                      label: Text('Selected for Trading'),
                      avatar: Icon(Icons.check, size: 16),
                      visualDensity: VisualDensity.compact,
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 24),

              // Price levels
              if (thesis.targetEntryPrice != null) ...[
                Text('Price Levels', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        _LevelBox(label: 'Entry', value: thesis.targetEntryPrice!, color: Colors.blue),
                        const SizedBox(width: 24),
                        if (thesis.stopLossPrice != null)
                          _LevelBox(label: 'Stop Loss', value: thesis.stopLossPrice!, color: Colors.orange),
                        if (thesis.stopLossPrice != null) const SizedBox(width: 24),
                        if (thesis.takeProfitPrice != null)
                          _LevelBox(label: 'Take Profit', value: thesis.takeProfitPrice!, color: Colors.teal),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 24),
              ],

              // Breach condition
              Text('Breach Condition', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      const Icon(Icons.warning_amber, color: Colors.orange),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(thesis.thesisBreachCondition, style: theme.textTheme.bodyMedium),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Sentry status
              if (sentrySignal != null) ...[
                Text('Latest Sentry Signal', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SentryBadge(signal: sentrySignal.signal),
                        const SizedBox(height: 8),
                        Text(sentrySignal.reasoning, style: theme.textTheme.bodyMedium),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 24),
              ],

              // Full reasoning
              Text('Analysis', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: SelectableText(thesis.reasoning, style: theme.textTheme.bodyMedium),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _LevelBox extends StatelessWidget {
  final String label;
  final double value;
  final Color color;

  const _LevelBox({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(label, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: color)),
        const SizedBox(height: 4),
        Text('\$${value.toStringAsFixed(2)}', style: monoStyle.copyWith(fontSize: 18, fontWeight: FontWeight.bold)),
      ],
    );
  }
}
