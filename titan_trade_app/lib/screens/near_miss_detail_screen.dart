import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../providers/near_miss_provider.dart';
import '../theme.dart';
import '../widgets/context_card.dart';
import '../widgets/gate_result_tile.dart';

class NearMissDetailScreen extends ConsumerWidget {
  final int nearMissIndex;

  const NearMissDetailScreen({super.key, required this.nearMissIndex});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final nearMisses = ref.watch(nearMissProvider);

    return nearMisses.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
      data: (list) {
        if (nearMissIndex >= list.length) {
          return const Center(child: Text('Near miss not found.'));
        }

        final nm = list[nearMissIndex];
        final dateStr = DateFormat('yyyy-MM-dd HH:mm:ss').format(nm.timestamp.toLocal());
        final closeness = nm.totalGatesFailed == 1 ? 'Very close' : 'Close';
        final closenessColor = nm.totalGatesFailed == 1 ? Colors.orange : Colors.amber;

        return Padding(
          padding: const EdgeInsets.all(24),
          child: ListView(
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.arrow_back),
                  label: const Text('Back'),
                ),
              ),
              const SizedBox(height: 8),

              // Header
              Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(nm.ticker, style: theme.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(width: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: closenessColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      '$closeness — ${nm.totalGatesFailed} gate(s) blocked',
                      style: TextStyle(color: closenessColor, fontWeight: FontWeight.bold),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text('${nm.thesis} (${nm.confidencePercent}%)', style: theme.textTheme.titleMedium),
                  const Spacer(),
                  Text(dateStr, style: theme.textTheme.bodySmall),
                ],
              ),
              const SizedBox(height: 24),

              // Gate results (the key section)
              Text('Risk Gate Results', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              GateResultsCard(gateResults: nm.gateResults),
              const SizedBox(height: 24),

              // Thesis that would have been traded
              Text('Thesis (Would Have Traded)', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (nm.targetEntryPrice != null)
                        Text(
                          'Entry: \$${nm.targetEntryPrice!.toStringAsFixed(2)}  |  '
                          'Stop: \$${nm.stopLossPrice?.toStringAsFixed(2) ?? "N/A"}  |  '
                          'Target: \$${nm.takeProfitPrice?.toStringAsFixed(2) ?? "N/A"}',
                          style: monoStyle.copyWith(fontSize: 13),
                        ),
                      const SizedBox(height: 12),
                      SelectableText(nm.reasoning, style: theme.textTheme.bodyMedium),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Market context
              if (nm.context != null) ...[
                Text('Market & Technical Context', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                TradeContextCard(context: nm.context!),
              ],
            ],
          ),
        );
      },
    );
  }
}
