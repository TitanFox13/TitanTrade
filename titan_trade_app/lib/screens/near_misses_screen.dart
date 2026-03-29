import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../providers/near_miss_provider.dart';

class NearMissesScreen extends ConsumerWidget {
  const NearMissesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final nearMisses = ref.watch(nearMissProvider);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Near Misses', style: theme.textTheme.headlineSmall),
          const SizedBox(height: 4),
          Text(
            'Trades blocked by 2 or fewer risk gates',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 16),
          Expanded(
            child: nearMisses.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(child: Text('Error: $e')),
              data: (list) {
                if (list.isEmpty) {
                  return const Center(child: Text('No near misses recorded yet.'));
                }
                return ListView.builder(
                  itemCount: list.length,
                  itemBuilder: (context, index) {
                    final nm = list[index];
                    final dateStr = DateFormat('yyyy-MM-dd HH:mm').format(nm.timestamp.toLocal());
                    final closeness = nm.totalGatesFailed == 1 ? 'Very close' : 'Close';
                    final closenessColor = nm.totalGatesFailed == 1 ? Colors.orange : Colors.amber;

                    return Card(
                      child: ListTile(
                        onTap: () => context.go('/near-misses/$index'),
                        leading: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: closenessColor.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            closeness,
                            style: TextStyle(color: closenessColor, fontWeight: FontWeight.bold, fontSize: 12),
                          ),
                        ),
                        title: Row(
                          children: [
                            Text(nm.ticker, style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                            const SizedBox(width: 8),
                            Text('${nm.thesis} (${nm.confidencePercent}%)', style: theme.textTheme.bodyMedium),
                          ],
                        ),
                        subtitle: Text(
                          '$dateStr  |  Blocked by: ${nm.failedGates.join(", ")}',
                          style: theme.textTheme.bodySmall,
                        ),
                        trailing: const Icon(Icons.chevron_right),
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
