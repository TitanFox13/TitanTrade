import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/trade.dart';
import '../theme.dart';

class TradeTile extends StatelessWidget {
  final Trade trade;
  final VoidCallback? onTap;

  const TradeTile({super.key, required this.trade, this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final dateStr = DateFormat('yyyy-MM-dd HH:mm').format(trade.timestamp.toLocal());
    final actionColor = trade.isBuy ? Colors.green : Colors.red;

    return Card(
      child: ListTile(
        onTap: onTap,
        leading: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: actionColor.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            trade.action,
            style: TextStyle(color: actionColor, fontWeight: FontWeight.bold, fontSize: 12),
          ),
        ),
        title: Row(
          children: [
            Text(trade.ticker, style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(width: 12),
            Text(
              '${trade.shares} @ \$${trade.price.toStringAsFixed(2)}',
              style: theme.textTheme.bodyMedium?.merge(monoStyle),
            ),
          ],
        ),
        subtitle: Text('$dateStr  |  Trigger: ${trade.trigger}', style: theme.textTheme.bodySmall),
        trailing: Text(
          '\$${trade.totalValue.toStringAsFixed(2)}',
          style: theme.textTheme.bodyMedium?.merge(monoStyle),
        ),
      ),
    );
  }
}
