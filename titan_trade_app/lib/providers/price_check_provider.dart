import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../models/price_check_signal.dart';
import 'config_provider.dart';

final priceCheckProvider = StreamProvider<PriceCheckResult?>((ref) async* {
  final urlAsync = ref.watch(baseUrlProvider);
  final refreshSeconds = ref.watch(refreshIntervalProvider);
  final baseUrl = urlAsync.valueOrNull;
  if (baseUrl == null) return;

  while (true) {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/pricecheck'));
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        if (json.containsKey('generated_at')) {
          yield PriceCheckResult.fromJson(json);
        } else {
          yield null;
        }
      } else {
        yield null;
      }
    } catch (_) {
      yield null;
    }
    await Future<void>.delayed(Duration(seconds: refreshSeconds));
  }
});
