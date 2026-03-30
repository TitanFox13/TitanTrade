import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../models/near_miss.dart';
import 'config_provider.dart';

final nearMissProvider = StreamProvider<List<NearMiss>>((ref) async* {
  final urlAsync = ref.watch(baseUrlProvider);
  final refreshSeconds = ref.watch(refreshIntervalProvider);
  final baseUrl = urlAsync.valueOrNull;
  if (baseUrl == null) return;

  while (true) {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/near-misses'));
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        final nearMisses = (json['near_misses'] as List<dynamic>)
            .map((nm) => NearMiss.fromJson(nm as Map<String, dynamic>))
            .toList()
          ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
        yield nearMisses;
      } else {
        yield [];
      }
    } catch (_) {
      yield [];
    }
    await Future<void>.delayed(Duration(seconds: refreshSeconds));
  }
});
