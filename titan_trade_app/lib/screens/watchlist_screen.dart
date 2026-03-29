import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/watchlist_provider.dart';

class WatchlistScreen extends ConsumerStatefulWidget {
  const WatchlistScreen({super.key});

  @override
  ConsumerState<WatchlistScreen> createState() => _WatchlistScreenState();
}

class _WatchlistScreenState extends ConsumerState<WatchlistScreen> {
  final _controller = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _addTicker() {
    final ticker = _controller.text.toUpperCase().trim();
    if (ticker.isEmpty) {
      setState(() => _error = 'Enter a ticker symbol.');
      return;
    }
    if (!RegExp(r'^[A-Z.]{1,10}$').hasMatch(ticker)) {
      setState(() => _error = 'Invalid ticker format.');
      return;
    }
    final current = ref.read(watchlistProvider).valueOrNull ?? [];
    if (current.contains(ticker)) {
      setState(() => _error = '$ticker is already in the watchlist.');
      return;
    }
    ref.read(watchlistProvider.notifier).addTicker(ticker);
    _controller.clear();
    setState(() => _error = null);
  }

  void _removeTicker(String ticker) {
    ref.read(watchlistProvider.notifier).removeTicker(ticker);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final watchlist = ref.watch(watchlistProvider);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Watchlist', style: theme.textTheme.headlineSmall),
          const SizedBox(height: 4),
          Text(
            'Stocks tracked by TitanTrade. Changes take effect on the next analysis run.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 16),

          // Add ticker input
          Row(
            children: [
              SizedBox(
                width: 200,
                child: TextField(
                  controller: _controller,
                  textCapitalization: TextCapitalization.characters,
                  decoration: InputDecoration(
                    labelText: 'Add ticker',
                    hintText: 'e.g. AAPL',
                    errorText: _error,
                    border: const OutlineInputBorder(),
                    isDense: true,
                  ),
                  onSubmitted: (_) => _addTicker(),
                ),
              ),
              const SizedBox(width: 12),
              FilledButton.icon(
                onPressed: _addTicker,
                icon: const Icon(Icons.add),
                label: const Text('Add'),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Watchlist
          Expanded(
            child: watchlist.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(child: Text('Error: $e')),
              data: (tickers) {
                if (tickers.isEmpty) {
                  return const Center(child: Text('Watchlist is empty.'));
                }
                return ListView.builder(
                  itemCount: tickers.length,
                  itemBuilder: (context, index) {
                    final ticker = tickers[index];
                    return Card(
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: theme.colorScheme.primaryContainer,
                          child: Text(
                            ticker.substring(0, ticker.length > 2 ? 2 : ticker.length),
                            style: TextStyle(color: theme.colorScheme.onPrimaryContainer, fontWeight: FontWeight.bold),
                          ),
                        ),
                        title: Text(ticker, style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                        trailing: IconButton(
                          icon: const Icon(Icons.delete_outline),
                          color: Colors.red,
                          onPressed: () => _showRemoveDialog(ticker),
                        ),
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

  void _showRemoveDialog(String ticker) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Remove $ticker?'),
        content: Text('$ticker will no longer be analyzed or traded. This takes effect on the next run.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              _removeTicker(ticker);
              Navigator.pop(ctx);
            },
            child: const Text('Remove'),
          ),
        ],
      ),
    );
  }
}
