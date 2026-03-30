import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../models/sentry_signal.dart';
import 'config_provider.dart';

final sentryProvider = StreamProvider<SentryBundle?>((ref) async* {
  final urlAsync = ref.watch(baseUrlProvider);
  final refreshSeconds = ref.watch(refreshIntervalProvider);
  final baseUrl = urlAsync.valueOrNull;
  if (baseUrl == null) return;

  while (true) {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/sentry'));
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        yield SentryBundle.fromJson(json);
      } else {
        yield null;
      }
    } catch (_) {
      yield null;
    }
    await Future<void>.delayed(Duration(seconds: refreshSeconds));
  }
});
