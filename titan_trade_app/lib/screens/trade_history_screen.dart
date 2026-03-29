import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/trade_log_provider.dart';
import '../widgets/trade_tile.dart';

class TradeHistoryScreen extends ConsumerStatefulWidget {
  const TradeHistoryScreen({super.key});

  @override
  ConsumerState<TradeHistoryScreen> createState() => _TradeHistoryScreenState();
}

class _TradeHistoryScreenState extends ConsumerState<TradeHistoryScreen> {
  String _filter = 'All';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final trades = ref.watch(tradeLogProvider);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Trade History', style: theme.textTheme.headlineSmall),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            children: ['All', 'BUY', 'SELL'].map((label) {
              return FilterChip(
                label: Text(label),
                selected: _filter == label,
                onSelected: (_) => setState(() => _filter = label),
              );
            }).toList(),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: trades.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(child: Text('Error: $e')),
              data: (list) {
                final filtered = _filter == 'All'
                    ? list
                    : list.where((t) => t.action == _filter).toList();

                if (filtered.isEmpty) {
                  return const Center(child: Text('No trades match the filter.'));
                }

                return ListView.builder(
                  itemCount: filtered.length,
                  itemBuilder: (context, index) {
                    final trade = filtered[index];
                    // Find the original index for navigation
                    final originalIndex = list.indexOf(trade);
                    return TradeTile(
                      trade: trade,
                      onTap: () => context.go('/trades/$originalIndex'),
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
