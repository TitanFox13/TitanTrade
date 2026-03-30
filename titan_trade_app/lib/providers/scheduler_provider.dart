import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import 'config_provider.dart';

class ScheduledJob {
  final String id;
  final String name;
  final String command;
  final Map<String, dynamic> cron;
  final bool enabled;
  final String? nextRun;
  final Map<String, dynamic>? lastRun;

  const ScheduledJob({
    required this.id,
    required this.name,
    required this.command,
    required this.cron,
    required this.enabled,
    this.nextRun,
    this.lastRun,
  });

  factory ScheduledJob.fromJson(Map<String, dynamic> json) {
    return ScheduledJob(
      id: json['id'] as String,
      name: json['name'] as String? ?? json['id'] as String,
      command: json['command'] as String,
      cron: json['cron'] as Map<String, dynamic>? ?? {},
      enabled: json['enabled'] as bool? ?? true,
      nextRun: json['next_run'] as String?,
      lastRun: json['last_run'] as Map<String, dynamic>?,
    );
  }

  String get lastStatus {
    if (lastRun == null) return 'never';
    return lastRun!['status'] as String? ?? 'unknown';
  }
}

final schedulerProvider =
    StreamProvider.autoDispose<List<ScheduledJob>>((ref) async* {
  final url = ref.watch(baseUrlProvider).valueOrNull;
  final interval = ref.watch(refreshIntervalProvider);

  while (true) {
    if (url != null) {
      try {
        final response = await http.get(Uri.parse('$url/api/scheduler'));
        if (response.statusCode == 200) {
          final json = jsonDecode(response.body) as Map<String, dynamic>;
          final jobs = (json['jobs'] as List<dynamic>? ?? [])
              .map((j) => ScheduledJob.fromJson(j as Map<String, dynamic>))
              .toList();
          yield jobs;
        }
      } catch (_) {
        // Skip cycle on error
      }
    }
    await Future.delayed(Duration(seconds: interval));
  }
});

Future<bool> triggerJob(String baseUrl, String jobId) async {
  try {
    final response = await http.post(
      Uri.parse('$baseUrl/api/scheduler/$jobId/trigger'),
    );
    return response.statusCode == 200;
  } catch (_) {
    return false;
  }
}

Future<bool> setJobEnabled(String baseUrl, String jobId, bool enabled) async {
  try {
    final response = await http.put(
      Uri.parse('$baseUrl/api/scheduler/$jobId/enabled'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'enabled': enabled}),
    );
    return response.statusCode == 200;
  } catch (_) {
    return false;
  }
}
