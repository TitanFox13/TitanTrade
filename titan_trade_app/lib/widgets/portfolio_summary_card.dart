import 'package:flutter/material.dart';

import '../models/portfolio.dart';
import '../theme.dart';
import 'pnl_chip.dart';

class PortfolioSummaryCard extends StatelessWidget {
  final Portfolio portfolio;

  const PortfolioSummaryCard({super.key, required this.portfolio});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            _Stat(
              label: 'Total Value',
              value: '\$${portfolio.totalValue.toStringAsFixed(2)}',
              style: theme.textTheme.headlineSmall!.merge(monoStyle),
            ),
            const SizedBox(width: 40),
            _Stat(label: 'Cash', value: '\$${portfolio.cashBalance.toStringAsFixed(2)}'),
            const SizedBox(width: 40),
            _Stat(label: 'Invested', value: '\$${portfolio.investedValue.toStringAsFixed(2)}'),
            const SizedBox(width: 40),
            _Stat(label: 'Positions', value: '${portfolio.positions.length}'),
            const SizedBox(width: 40),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Unrealized P&L', style: theme.textTheme.bodySmall),
                const SizedBox(height: 4),
                PnlChip(value: portfolio.totalUnrealizedPnl),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  final TextStyle? style;

  const _Stat({required this.label, required this.value, this.style});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: theme.textTheme.bodySmall),
        const SizedBox(height: 4),
        Text(value, style: style ?? theme.textTheme.titleMedium!.merge(monoStyle)),
      ],
    );
  }
}
