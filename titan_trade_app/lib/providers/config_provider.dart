import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';

final dataPathProvider = StateNotifierProvider<DataPathNotifier, AsyncValue<String?>>((ref) {
  return DataPathNotifier();
});

class DataPathNotifier extends StateNotifier<AsyncValue<String?>> {
  DataPathNotifier() : super(const AsyncValue.loading()) {
    _load();
  }

  Future<void> _load() async {
    final path = await loadDataPath();
    state = AsyncValue.data(path);
  }

  Future<void> setPath(String path) async {
    await saveDataPath(path);
    state = AsyncValue.data(path);
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
