import React from 'react';
import { Badge } from './badge';
import { Button } from './button';
import { Card, CardContent, CardHeader, CardTitle } from './card';

export interface TimelineItem {
  id: string;
  title: string;
  description: string;
  date: string;
  status?: 'completed' | 'in-progress' | 'pending';
}

export interface RadialOrbitalTimelineProps {
  timelineData: TimelineItem[];
}

export function RadialOrbitalTimeline({ timelineData }: RadialOrbitalTimelineProps) {
  return (
    <Card className="w-full max-w-3xl mx-auto bg-white/40 backdrop-blur-md border-white/60 shadow-lg">
      <CardHeader>
        <CardTitle className="text-slate-800">Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative pl-8 border-l-2 border-mint-200 space-y-8">
          {timelineData.map((item, index) => (
            <div key={item.id} className="relative">
              {/* Orbital node */}
              <div className="absolute -left-[41px] top-1 w-6 h-6 rounded-full bg-cyan-100 border-2 border-mint-400 flex items-center justify-center shadow-[0_0_10px_rgba(103,232,249,0.5)]">
                <div className="w-2 h-2 rounded-full bg-cyan-500" />
              </div>
              
              {/* Content */}
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h4 className="text-lg font-semibold text-slate-800">{item.title}</h4>
                  {item.status && (
                    <Badge variant={item.status === 'completed' ? 'default' : 'secondary'} className="bg-lavender-100 text-slate-700 hover:bg-lavender-200">
                      {item.status}
                    </Badge>
                  )}
                </div>
                <div className="text-sm font-medium text-cyan-600 mb-2">{item.date}</div>
                <p className="text-slate-600 text-sm leading-relaxed">{item.description}</p>
                <div className="mt-3">
                  <Button variant="outline" size="sm" className="border-cyan-200 hover:bg-cyan-50 text-cyan-700">
                    View Details
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default RadialOrbitalTimeline;
