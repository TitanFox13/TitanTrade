import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';

final baseUrlProvider = StateNotifierProvider<BaseUrlNotifier, AsyncValue<String?>>((ref) {
  return BaseUrlNotifier();
});

class BaseUrlNotifier extends StateNotifier<AsyncValue<String?>> {
  BaseUrlNotifier() : super(const AsyncValue.loading()) {
    _load();
  }

  Future<void> _load() async {
    final url = await loadBaseUrl();
    state = AsyncValue.data(url);
  }

  Future<void> setUrl(String url) async {
    await saveBaseUrl(url);
    state = AsyncValue.data(url);
  }
}

final refreshIntervalProvider = StateNotifierProvider<RefreshIntervalNotifier, int>((ref) {
  return RefreshIntervalNotifier();
});

class RefreshIntervalNotifier extends StateNotifier<int> {
  RefreshIntervalNotifier() : super(defaultRefreshSeconds) {
    _load();
  }

  Future<void> _load() async {
    state = await loadRefreshInterval();
  }

  Future<void> set(int seconds) async {
    await saveRefreshInterval(seconds);
    state = seconds;
  }
}
