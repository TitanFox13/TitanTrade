import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;

import 'config_provider.dart';

final watchlistProvider = StateNotifierProvider<WatchlistNotifier, AsyncValue<List<String>>>((ref) {
  final pathAsync = ref.watch(dataPathProvider);
  return WatchlistNotifier(pathAsync.valueOrNull);
});

class WatchlistNotifier extends StateNotifier<AsyncValue<List<String>>> {
  final String? _rootPath;

  WatchlistNotifier(this._rootPath) : super(const AsyncValue.loading()) {
    _load();
  }

  String? get _filePath =>
      _rootPath != null ? p.join(_rootPath, 'data', 'watchlist.json') : null;

  Future<void> _load() async {
    final path = _filePath;
    if (path == null) {
      state = const AsyncValue.data([]);
      return;
    }
    final file = File(path);
    if (!file.existsSync()) {
      state = const AsyncValue.data([]);
      return;
    }
    try {
      final json = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
      final tickers = (json['watchlist'] as List<dynamic>).map((t) => t as String).toList();
      state = AsyncValue.data(tickers);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> addTicker(String ticker) async {
    final current = state.valueOrNull ?? [];
    final upper = ticker.toUpperCase().trim();
    if (upper.isEmpty || current.contains(upper)) return;
    final updated = [...current, upper];
    await _save(updated);
    state = AsyncValue.data(updated);
  }

  Future<void> removeTicker(String ticker) async {
    final current = state.valueOrNull ?? [];
    final updated = current.where((t) => t != ticker).toList();
    await _save(updated);
    state = AsyncValue.data(updated);
  }

  Future<void> _save(List<String> tickers) async {
    final path = _filePath;
    if (path == null) return;
    final file = File(path);

    Map<String, dynamic> data;
    if (file.existsSync()) {
      data = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
    } else {
      data = {
        'settings': {'risk_per_trade': 0.10, 'trading_mode': 'paper', 'stop_loss_pct': 0.05}
      };
    }
    data['watchlist'] = tickers;
    file.writeAsStringSync(const JsonEncoder.withIndent('  ').convert(data));
  }
}
