import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import 'config_provider.dart';

class TradingModeState {
  final String mode; // "paper" or "live"
  final bool liveKeysConfigured;

  const TradingModeState({
    this.mode = 'paper',
    this.liveKeysConfigured = false,
  });

  bool get isLive => mode == 'live';
}

final tradingModeProvider =
    StateNotifierProvider<TradingModeNotifier, AsyncValue<TradingModeState>>((ref) {
  final urlAsync = ref.watch(baseUrlProvider);
  return TradingModeNotifier(urlAsync.valueOrNull);
});

class TradingModeNotifier extends StateNotifier<AsyncValue<TradingModeState>> {
  final String? _baseUrl;

  TradingModeNotifier(this._baseUrl) : super(const AsyncValue.loading()) {
    _load();
  }

  Future<void> _load() async {
    final url = _baseUrl;
    if (url == null) {
      state = const AsyncValue.data(TradingModeState());
      return;
    }
    try {
      final response = await http.get(Uri.parse('$url/api/settings'));
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        state = AsyncValue.data(TradingModeState(
          mode: json['trading_mode'] as String? ?? 'paper',
          liveKeysConfigured: json['live_keys_configured'] as bool? ?? false,
        ));
      } else {
        state = const AsyncValue.data(TradingModeState());
      }
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<bool> setMode(String mode) async {
    final url = _baseUrl;
    if (url == null) return false;
    try {
      final response = await http.put(
        Uri.parse('$url/api/settings/mode'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'trading_mode': mode}),
      );
      if (response.statusCode == 200) {
        final current = state.valueOrNull ?? const TradingModeState();
        state = AsyncValue.data(TradingModeState(
          mode: mode,
          liveKeysConfigured: current.liveKeysConfigured,
        ));
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }
}
