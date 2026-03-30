import 'package:flutter/material.dart';

import '../models/portfolio.dart';
import '../models/trailing_stop.dart';
import '../theme.dart';
import 'pnl_chip.dart';

class PositionTile extends StatelessWidget {
  final Position position;
  final TrailingStopState? trailingStop;

  const PositionTile({super.key, required this.position, this.trailingStop});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final ts = trailingStop;

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
            if (ts != null && ts.trailingActive) ...[
              const SizedBox(width: 8),
              Tooltip(
                message: 'Trailing stop active — HWM \$${ts.highWaterMark.toStringAsFixed(2)}',
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.teal.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    'TRAIL',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: Colors.tealAccent,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
        subtitle: Row(
          children: [
            if (position.currentPrice != null)
              Text(
                'Now \$${position.currentPrice!.toStringAsFixed(2)}',
                style: theme.textTheme.bodySmall?.merge(monoStyle),
              ),
            if (ts != null && ts.trailingActive && ts.trailingStopPrice != null) ...[
              const SizedBox(width: 16),
              Text(
                'Trail \$${ts.trailingStopPrice!.toStringAsFixed(2)}',
                style: theme.textTheme.bodySmall?.copyWith(color: Colors.tealAccent),
              ),
            ] else if (position.stopLossPrice != null) ...[
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
