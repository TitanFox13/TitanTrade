import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../providers/thesis_provider.dart';
import '../widgets/thesis_card.dart';

class ThesesScreen extends ConsumerWidget {
  const ThesesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final bundle = ref.watch(thesisProvider);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Active Theses', style: theme.textTheme.headlineSmall),
          const SizedBox(height: 8),
          bundle.when(
            loading: () => const SizedBox.shrink(),
            error: (e, st) => const SizedBox.shrink(),
            data: (b) {
              if (b == null) return const SizedBox.shrink();
              final generated = DateFormat('yyyy-MM-dd HH:mm').format(b.generatedAt.toLocal());
              final daysLeft = b.timeUntilExpiry.inDays;
              final expiryLabel = b.isExpired ? 'EXPIRED' : '$daysLeft days left';
              final expiryColor = b.isExpired ? Colors.red : Colors.grey;
              return Text(
                'Generated $generated  |  $expiryLabel',
                style: theme.textTheme.bodySmall?.copyWith(color: expiryColor),
              );
            },
          ),
          const SizedBox(height: 16),
          Expanded(
            child: bundle.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(child: Text('Error: $e')),
              data: (b) {
                if (b == null || b.theses.isEmpty) {
                  return const Center(child: Text('No theses generated yet.'));
                }
                return LayoutBuilder(
                  builder: (context, constraints) {
                    final crossAxisCount = constraints.maxWidth > 900 ? 3 : 2;
                    return GridView.builder(
                      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: crossAxisCount,
                        childAspectRatio: 1.4,
                        crossAxisSpacing: 12,
                        mainAxisSpacing: 12,
                      ),
                      itemCount: b.theses.length,
                      itemBuilder: (context, index) {
                        final thesis = b.theses[index];
                        return ThesisCard(
                          thesis: thesis,
                          onTap: () => context.go('/theses/${thesis.ticker}'),
                        );
                      },
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
