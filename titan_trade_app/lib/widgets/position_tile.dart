import 'package:flutter/material.dart';

import '../models/portfolio.dart';
import '../theme.dart';
import 'pnl_chip.dart';

class PositionTile extends StatelessWidget {
  final Position position;

  const PositionTile({super.key, required this.position});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: ListTile(
        title: Row(
          children: [
            Text(position.ticker, style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(width: 12),
            Text(
              '${position.shares} shares @ \$${position.entryPrice.toStringAsFixed(2)}',
              style: theme.textTheme.bodyMedium?.merge(monoStyle),
            ),
          ],
        ),
        subtitle: Row(
          children: [
            if (position.currentPrice != null)
              Text(
                'Now \$${position.currentPrice!.toStringAsFixed(2)}',
                style: theme.textTheme.bodySmall?.merge(monoStyle),
              ),
            if (position.stopLossPrice != null) ...[
              const SizedBox(width: 16),
              Text(
                'Stop \$${position.stopLossPrice!.toStringAsFixed(2)}',
                style: theme.textTheme.bodySmall?.copyWith(color: Colors.orange),
              ),
            ],
          ],
        ),
        trailing: PnlChip(
          value: position.unrealizedPnl ?? 0,
          percent: position.pnlPercent,
        ),
      ),
    );
  }
}
