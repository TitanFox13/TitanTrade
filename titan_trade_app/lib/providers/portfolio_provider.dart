import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../models/portfolio.dart';
import 'config_provider.dart';

final portfolioProvider = StreamProvider<Portfolio>((ref) async* {
  final urlAsync = ref.watch(baseUrlProvider);
  final refreshSeconds = ref.watch(refreshIntervalProvider);
  final baseUrl = urlAsync.valueOrNull;
  if (baseUrl == null) return;

  while (true) {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/portfolio'));
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        yield Portfolio.fromJson(json);
      }
    } catch (_) {
      // Network error — skip this cycle
    }
    await Future<void>.delayed(Duration(seconds: refreshSeconds));
  }
});
