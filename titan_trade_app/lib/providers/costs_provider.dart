import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../models/cost_record.dart';
import 'config_provider.dart';

final costsProvider = StreamProvider<List<CostRecord>>((ref) async* {
  final urlAsync = ref.watch(baseUrlProvider);
  final refreshSeconds = ref.watch(refreshIntervalProvider);
  final baseUrl = urlAsync.valueOrNull;
  if (baseUrl == null) {
    yield [];
    return;
  }

  while (true) {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/costs'));
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        final list = (json['costs'] as List<dynamic>?) ?? [];
        final records = list
            .map((e) => CostRecord.fromJson(e as Map<String, dynamic>))
            .toList()
          ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
        yield records;
      } else {
        yield [];
      }
    } catch (_) {
      yield [];
    }
    await Future<void>.delayed(Duration(seconds: refreshSeconds));
  }
});
