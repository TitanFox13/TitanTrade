import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../providers/config_provider.dart';
import '../providers/scheduler_provider.dart';

class SchedulerScreen extends ConsumerWidget {
  const SchedulerScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final jobsAsync = ref.watch(schedulerProvider);

    return Scaffold(
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text('Scheduler', style: theme.textTheme.headlineMedium),
          const SizedBox(height: 8),
          Text(
            'Automated trading jobs running inside the backend.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 24),
          jobsAsync.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Text(
              'Could not load scheduler status.',
              style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.error),
            ),
            data: (jobs) => Column(
              children: jobs.map((job) => _JobCard(job: job)).toList(),
            ),
          ),
        ],
      ),
    );
  }
}

class _JobCard extends ConsumerWidget {
  final ScheduledJob job;

  const _JobCard({required this.job});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final baseUrl = ref.watch(baseUrlProvider).valueOrNull;

    final statusColor = switch (job.lastStatus) {
      'completed' => Colors.green,
      'failed' => Colors.red,
      'running' => Colors.orange,
      _ => Colors.grey,
    };

    final statusIcon = switch (job.lastStatus) {
      'completed' => Icons.check_circle,
      'failed' => Icons.error,
      'running' => Icons.sync,
      _ => Icons.schedule,
    };

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(statusIcon, color: statusColor, size: 28),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    job.name,
                    style: theme.textTheme.titleSmall?.copyWith(
                      color: job.enabled ? null : theme.disabledColor,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _formatCron(job.cron),
                    style: theme.textTheme.bodySmall,
                  ),
                  if (job.nextRun != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      'Next: ${_formatTime(job.nextRun!)}',
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                  if (job.lastRun != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      'Last: ${_formatTime(job.lastRun!['started_at'] as String? ?? '')} '
                      '(${job.lastStatus}${_lastResult(job)})',
                      style: theme.textTheme.bodySmall?.copyWith(color: statusColor),
                    ),
                  ],
                ],
              ),
            ),
            Switch(
              value: job.enabled,
              onChanged: baseUrl == null
                  ? null
                  : (val) => setJobEnabled(baseUrl, job.id, val),
            ),
            const SizedBox(width: 8),
            IconButton(
              icon: const Icon(Icons.play_arrow),
              tooltip: 'Run now',
              onPressed: baseUrl == null
                  ? null
                  : () async {
                      final ok = await triggerJob(baseUrl, job.id);
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(ok
                                ? '${job.name} triggered'
                                : 'Failed to trigger ${job.name}'),
                            duration: const Duration(seconds: 2),
                          ),
                        );
                      }
                    },
            ),
          ],
        ),
      ),
    );
  }

  String _formatCron(Map<String, dynamic> cron) {
    final dow = cron['day_of_week'] ?? '*';
    final h = cron['hour']?.toString().padLeft(2, '0') ?? '**';
    final m = cron['minute']?.toString().padLeft(2, '0') ?? '**';
    return '$dow at $h:$m UTC';
  }

  String _formatTime(String iso) {
    if (iso.isEmpty) return '';
    try {
      final dt = DateTime.parse(iso);
      return DateFormat('MMM d HH:mm').format(dt);
    } catch (_) {
      return iso;
    }
  }

  String _lastResult(ScheduledJob job) {
    final result = job.lastRun?['result'];
    if (result == null) return '';
    return ' - $result';
  }
}
