import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../models/trailing_stop.dart';
import 'config_provider.dart';

final trailingStopsProvider = StreamProvider<Map<String, TrailingStopState>>((ref) async* {
  final urlAsync = ref.watch(baseUrlProvider);
  final refreshSeconds = ref.watch(refreshIntervalProvider);
  final baseUrl = urlAsync.valueOrNull;
  if (baseUrl == null) return;

  while (true) {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/trailing-stops'));
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        yield TrailingStopState.fromJson(json);
      } else {
        yield {};
      }
    } catch (_) {
      yield {};
    }
    await Future<void>.delayed(Duration(seconds: refreshSeconds));
  }
});
