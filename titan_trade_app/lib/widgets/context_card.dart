import 'package:flutter/material.dart';

import '../models/near_miss.dart';
import '../theme.dart';

class TradeContextCard extends StatelessWidget {
  final TradeContext context;

  const TradeContextCard({super.key, required this.context});

  @override
  Widget build(BuildContext ctx) {
    final theme = Theme.of(ctx);
    final tech = context.technicals;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Market Context', style: theme.textTheme.titleSmall),
            const Divider(),
            Wrap(
              spacing: 24,
              runSpacing: 8,
              children: [
                if (context.marketRegime != null)
                  _ContextChip(label: 'Regime', value: context.marketRegime!),
                if (context.vixLevel != null)
                  _ContextChip(
                    label: 'VIX',
                    value: '${context.vixLevel!.toStringAsFixed(1)} (${context.vixClassification ?? ""})',
                  ),
                if (context.spyReturn1d != null)
                  _ContextChip(label: 'SPY 1d', value: '${context.spyReturn1d! >= 0 ? "+" : ""}${context.spyReturn1d!.toStringAsFixed(2)}%'),
                if (context.sector != null)
                  _ContextChip(label: 'Sector', value: context.sector!),
                if (context.earningsDaysAway != null)
                  _ContextChip(label: 'Earnings in', value: '${context.earningsDaysAway} days'),
              ],
            ),
            if (tech != null) ...[
              const SizedBox(height: 12),
              Text('Technical Indicators', style: theme.textTheme.titleSmall),
              const SizedBox(height: 8),
              Wrap(
                spacing: 24,
                runSpacing: 8,
                children: [
                  if (tech.rsi14 != null)
                    _ContextChip(label: 'RSI(14)', value: tech.rsi14!.toStringAsFixed(1)),
                  if (tech.macdHistogram != null)
                    _ContextChip(label: 'MACD Hist', value: tech.macdHistogram!.toStringAsFixed(2)),
                  if (tech.atr14 != null)
                    _ContextChip(label: 'ATR(14)', value: '\$${tech.atr14!.toStringAsFixed(2)}'),
                  if (tech.priceVsSma50 != null)
                    _ContextChip(label: 'vs SMA50', value: tech.priceVsSma50!),
                  if (tech.priceVsSma200 != null)
                    _ContextChip(label: 'vs SMA200', value: tech.priceVsSma200!),
                ],
              ),
            ],
            if (context.recentNews.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text('Recent Headlines', style: theme.textTheme.titleSmall),
              const SizedBox(height: 4),
              ...context.recentNews.map(
                (headline) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('- ', style: monoStyle),
                      Expanded(child: Text(headline, style: theme.textTheme.bodySmall)),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ContextChip extends StatelessWidget {
  final String label;
  final String value;

  const _ContextChip({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(label, style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
        Text(value, style: theme.textTheme.bodyMedium?.merge(monoStyle)),
      ],
    );
  }
}
