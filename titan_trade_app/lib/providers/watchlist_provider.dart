import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import 'config_provider.dart';

final watchlistProvider = StateNotifierProvider<WatchlistNotifier, AsyncValue<List<String>>>((ref) {
  final urlAsync = ref.watch(baseUrlProvider);
  return WatchlistNotifier(urlAsync.valueOrNull);
});

class WatchlistNotifier extends StateNotifier<AsyncValue<List<String>>> {
  final String? _baseUrl;

  WatchlistNotifier(this._baseUrl) : super(const AsyncValue.loading()) {
    _load();
  }

  Future<void> _load() async {
    final url = _baseUrl;
    if (url == null) {
      state = const AsyncValue.data([]);
      return;
    }
    try {
      final response = await http.get(Uri.parse('$url/api/watchlist'));
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        final tickers = (json['watchlist'] as List<dynamic>? ?? [])
            .map((t) => t as String)
            .toList();
        state = AsyncValue.data(tickers);
      } else {
        state = const AsyncValue.data([]);
      }
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> addTicker(String ticker) async {
    final current = state.valueOrNull ?? [];
    final upper = ticker.toUpperCase().trim();
    if (upper.isEmpty || current.contains(upper)) return;
    await _save([...current, upper]);
  }

  Future<void> removeTicker(String ticker) async {
    final current = state.valueOrNull ?? [];
    await _save(current.where((t) => t != ticker).toList());
  }

  Future<void> _save(List<String> tickers) async {
    final url = _baseUrl;
    if (url == null) return;
    try {
      final response = await http.put(
        Uri.parse('$url/api/watchlist'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'watchlist': tickers}),
      );
      if (response.statusCode == 200) {
        state = AsyncValue.data(tickers);
      }
    } catch (_) {
      // Leave state unchanged on network error
    }
  }
}
