import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../models/trade.dart';
import 'config_provider.dart';

final tradeLogProvider = StreamProvider<List<Trade>>((ref) async* {
  final urlAsync = ref.watch(baseUrlProvider);
  final refreshSeconds = ref.watch(refreshIntervalProvider);
  final baseUrl = urlAsync.valueOrNull;
  if (baseUrl == null) return;

  while (true) {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/trades'));
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        final trades = (json['trades'] as List<dynamic>)
            .map((t) => Trade.fromJson(t as Map<String, dynamic>))
            .toList()
          ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
        yield trades;
      } else {
        yield [];
      }
    } catch (_) {
      yield [];
    }
    await Future<void>.delayed(Duration(seconds: refreshSeconds));
  }
});
