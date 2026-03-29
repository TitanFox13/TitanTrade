import 'package:flutter/material.dart';

import '../models/thesis.dart';

class ThesisCard extends StatelessWidget {
  final Thesis thesis;
  final VoidCallback? onTap;

  const ThesisCard({super.key, required this.thesis, this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    final thesisColor = switch (thesis.thesis) {
      'BULLISH' => Colors.green,
      'BEARISH' => Colors.red,
      _ => Colors.grey,
    };

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    thesis.ticker,
                    style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: thesisColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      thesis.thesis,
                      style: TextStyle(
                        color: thesisColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ),
              if (thesis.sector != null) ...[
                const SizedBox(height: 4),
                Text(thesis.sector!, style: theme.textTheme.bodySmall),
              ],
              const SizedBox(height: 12),
              // Confidence bar
              Row(
                children: [
                  Text('Confidence', style: theme.textTheme.bodySmall),
                  const SizedBox(width: 8),
                  Expanded(
                    child: LinearProgressIndicator(
                      value: thesis.confidence,
                      backgroundColor: theme.colorScheme.surfaceContainerHighest,
                      color: thesis.confidence >= 0.7 ? Colors.teal : Colors.orange,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text('${thesis.confidencePercent}%', style: theme.textTheme.bodySmall),
                ],
              ),
              const SizedBox(height: 12),
              if (thesis.targetEntryPrice != null)
                _PriceRow(label: 'Entry', price: thesis.targetEntryPrice!),
              if (thesis.stopLossPrice != null)
                _PriceRow(label: 'Stop', price: thesis.stopLossPrice!, color: Colors.orange),
              if (thesis.takeProfitPrice != null)
                _PriceRow(label: 'Target', price: thesis.takeProfitPrice!, color: Colors.teal),
              const SizedBox(height: 8),
              if (thesis.selectedForTrading)
                Chip(
                  label: const Text('Selected for Trading'),
                  avatar: const Icon(Icons.check, size: 16),
                  visualDensity: VisualDensity.compact,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PriceRow extends StatelessWidget {
  final String label;
  final double price;
  final Color? color;

  const _PriceRow({required this.label, required this.price, this.color});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 2),
      child: Row(
        children: [
          SizedBox(
            width: 50,
            child: Text(label, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: color)),
          ),
          Text(
            '\$${price.toStringAsFixed(2)}',
            style: const TextStyle(fontFamily: 'Consolas', fontFamilyFallback: ['monospace'], fontSize: 13),
          ),
        ],
      ),
    );
  }
}
