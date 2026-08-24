using TriageApi.Api.Authorization;
using TriageApi.Api.Configuration;
using TriageApi.Api.Infrastructure;
using TriageApi.Core.Authorization;
using TriageApi.Core.Redaction;
using TriageApi.Core.Repositories;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.

builder.Services.AddControllers();
// Learn more about configuring Swagger/OpenAPI at https://aka.ms/aspnetcore/swashbuckle
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.Configure<MongoOptions>(builder.Configuration.GetSection(MongoOptions.SectionName));
builder.Services.AddSingleton<MongoContext>();
builder.Services.AddScoped<INotificationRepository, MongoNotificationRepository>();
builder.Services.AddScoped<ICustomerEventRepository, MongoCustomerEventRepository>();
builder.Services.AddScoped<IAuthorizationProvider, MongoAuthorizationProvider>();
builder.Services.AddScoped<ICurrentCaller, CurrentCaller>();
builder.Services.AddSingleton<IMessageRedactor, XmlAllowListRedactor>();

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

// Dev-only identity resolution (X-User-Id header). Replace with real IAM/JWT
// authentication middleware before this runs against real data - see README.
app.UseMiddleware<CallerIdentityMiddleware>();

app.UseAuthorization();

app.MapControllers();

app.Run();
